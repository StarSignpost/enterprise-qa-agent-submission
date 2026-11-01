"""Offline engineering verification. Scripted choices do not prove model quality."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.agent import Agent, Recorder
from src.cli import main
from src.mock_model import MockAdapter
from src.models import ModelError
from src.tools import KnowledgeTools

ROOT = Path(__file__).resolve().parents[1]


def action(name, **arguments):
    arguments.setdefault("decision_summary", "根据已收到的观察选择此动作")
    return {"name": name, "arguments": arguments}


def search(query="报销期限"):
    return action("search_documents", query=query, limit=5)


def read(document_id="D01"):
    return action("read_document", document_id=document_id, start=0, length=500)


def citation(call_id="mock-2", document_id="D01", quote="报销期限 30 天。", version_date="2026-10-01"):
    return {"document_id": document_id, "version_date": version_date, "quote": quote,
            "start": 0, "end": len(quote), "read_call_id": call_id}


def answer(text="报销期限为 30 天。", citations=None):
    return action("answer", answer=text, citations=[citation()] if citations is None else citations, gaps=[])


def review(verdict="supported"):
    return {"name": "assess_answer", "arguments": {"verdict": verdict,
            "reason": "引用可支持候选结论" if verdict == "supported" else "期限条款不能证明报销项目范围"}}


def stop(status="incomplete"):
    return action("stop", answer="未取得足够资料，无法完成。", citations=[],
                  gaps=["需要相关制度或恢复原文读取"], status=status)


class RecordingMock(MockAdapter):
    def __init__(self, actions):
        super().__init__(actions)
        self.requests = []

    def decide(self, budget, review=None):
        self.requests.append({"items": copy.deepcopy(self.items), "budget": dict(budget), "review": review})
        return super().decide(budget, review)


class AgentTests(unittest.TestCase):
    def run_script(self, actions, scenario="normal", max_steps=8, history=None, question="报销期限多久？"):
        tools = KnowledgeTools.from_file(ROOT / "data/scenarios" / f"{scenario}.json")
        adapter = RecordingMock(actions)
        recorder = Recorder(adapter.mode, adapter.model)
        output = Agent(tools, adapter, recorder).run(question, history, max_steps)
        return output, adapter, recorder

    def test_success_feedback_loop_and_separate_semantic_review(self):
        output, adapter, trace = self.run_script([search(), read(), answer(), review()])
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["mode"], "mock")
        self.assertEqual(output["steps_used"], 4)
        self.assertEqual(output["api_calls"], 0)
        observed = [i for i in adapter.requests[2]["items"] if i.get("type") == "function_call_output"]
        self.assertEqual(json.loads(observed[-1]["output"])["data"]["text"], "报销期限 30 天。")
        self.assertIsNotNone(adapter.requests[3]["review"])
        self.assertEqual(output["verification"]["semantic_support"]["verdict"], "supported")
        self.assertTrue(any(e["event"] == "transition" and e["next_action"] == "read_document" for e in trace.events))

    def test_successful_read_exposes_trusted_handle_in_model_visible_body(self):
        output, adapter, trace = self.run_script([search(), read(), answer(), review()])
        observed = adapter.observations["mock-2"]["data"]
        self.assertEqual(observed["read_call_id"], "mock-2")
        actual = json.loads(adapter.requests[2]["items"][-1]["output"])
        self.assertEqual(actual["data"]["read_call_id"], "mock-2")
        self.assertEqual(output["citations"][0]["read_call_id"], observed["read_call_id"])

    def test_citation_error_feedback_lists_only_successful_reads(self):
        bad = answer(citations=[{**citation(), "read_call_id": "invented"}])
        output, adapter, _ = self.run_script([search(), read(), bad, stop()])
        available = adapter.observations["mock-3"]["error"]["available_reads"]
        self.assertEqual([item["read_call_id"] for item in available], ["mock-2"])
        self.assertEqual([item["document_id"] for item in available], ["D01"])
        output, adapter, _ = self.run_script([search(), read(), bad, stop("failed")], "tool_error")
        self.assertEqual(adapter.observations["mock-3"]["error"]["available_reads"], [])

    def test_conflict_evidence_then_model_clarifies(self):
        clarify = action("clarify", answer="D01 为 30 天，D02 为 15 天；请确认适用制度。",
                         citations=[citation(), citation("mock-3", "D02", "报销期限 15 天。", "2026-10-15")],
                         gaps=["两份制度没有明确适用范围和优先级"])
        output, adapter, _ = self.run_script([search(), read(), read("D02"), search("适用范围 优先级"), clarify], "conflict")
        self.assertEqual(output["status"], "needs_clarification")
        self.assertEqual(len(output["citations"]), 2)
        self.assertEqual(adapter.observations["mock-4"]["data"]["matches"], [])

    def test_outside_corpus_and_ambiguous_question_are_not_forced_answers(self):
        output, _, _ = self.run_script([search(), stop()], "no_match")
        self.assertEqual(output["status"], "incomplete")
        clarify = action("clarify", answer="请说明查询什么事项？", citations=[], gaps=["缺少事项或制度名称"])
        output, _, _ = self.run_script([clarify], "ambiguous", question="多久？")
        self.assertEqual(output["status"], "needs_clarification")
        self.assertEqual(output["tool_calls"], 0)

    def test_tool_error_reaches_next_model_decision(self):
        final = stop("failed")
        final["expect"] = {"mock-2": {"ok": False, "error": {"code": "TOOL_UNAVAILABLE"}}}
        output, adapter, _ = self.run_script([search(), read(), final], "tool_error")
        self.assertEqual(output["status"], "failed")
        self.assertEqual(output["termination_source"], "model")
        result = json.loads(adapter.requests[2]["items"][-1]["output"])
        self.assertFalse(result["ok"])
        self.assertNotIn("data", result)

    def test_unexpected_tool_exception_is_observed_not_swallowed(self):
        class BrokenTools(KnowledgeTools):
            def search_documents(self, query, limit=5):
                raise RuntimeError("sensitive detail must not appear")
        adapter = RecordingMock([search(), stop("failed")])
        trace = Recorder("mock", adapter.model)
        output = Agent(BrokenTools([]), adapter, trace).run("问题")
        self.assertEqual(output["status"], "failed")
        self.assertEqual(adapter.observations["mock-1"]["error"]["code"], "TOOL_EXECUTION_ERROR")
        self.assertNotIn("sensitive detail", json.dumps(trace.events))

    def test_history_is_passed_in_original_order_without_topic_rewrite(self):
        history = [{"role": "user", "content": "差旅报销期限多久？"}, {"role": "assistant", "content": "此前回答"}]
        fragment = "差旅报销需提交发票和出差审批单。"
        script = [search("差旅报销材料"), read("D03"),
                  answer("需提交发票和出差审批单。", [citation(document_id="D03", quote=fragment)]), review()]
        output, adapter, _ = self.run_script(script, history=history, question="那需要什么材料？")
        self.assertEqual(output["status"], "completed")
        self.assertEqual(adapter.requests[0]["items"][:2], history)
        self.assertEqual(adapter.requests[0]["items"][-1]["content"], "那需要什么材料？")

    def test_unknown_actions_consume_budget(self):
        output, _, _ = self.run_script([action("invent_action"), action("invent_action")], max_steps=2)
        self.assertEqual(output["error_code"], "EXECUTION_LIMIT")
        self.assertEqual(output["steps_used"], 2)
        self.assertEqual(output["tool_calls"], 0)

    def test_invalid_json_can_be_reported_and_repaired(self):
        class InvalidJSONAdapter(RecordingMock):
            def decide(self, budget, review=None):
                reply = super().decide(budget, review)
                if self.position == 1:
                    reply["calls"][0]["arguments"] = "{broken json"
                return reply
        adapter = InvalidJSONAdapter([search(), stop()])
        output = Agent(KnowledgeTools([]), adapter).run("问题")
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(adapter.observations["mock-1"]["error"]["code"], "INVALID_ARGUMENT")
        self.assertEqual(output["steps_used"], 2)

    def test_multiple_calls_are_rejected_without_executing_any(self):
        class MultipleAdapter(RecordingMock):
            def decide(self, budget, review=None):
                reply = super().decide(budget, review)
                if self.position == 1:
                    reply["calls"].append({**reply["calls"][0], "call_id": "extra-call"})
                return reply
        adapter = MultipleAdapter([search(), stop()])
        output = Agent(KnowledgeTools([]), adapter).run("问题")
        self.assertEqual(output["tool_calls"], 0)
        self.assertEqual(adapter.observations["extra-call"]["error"]["code"], "ONE_ACTION_REQUIRED")

    def test_boolean_and_out_of_range_tool_parameters_are_errors(self):
        for limit in (True, 0, 21):
            with self.subTest(limit=limit):
                output, adapter, _ = self.run_script([action("search_documents", query="报销", limit=limit), stop()])
                self.assertEqual(output["status"], "incomplete")
                self.assertEqual(adapter.observations["mock-1"]["error"]["code"], "INVALID_ARGUMENT")

    def test_tool_at_limit_cannot_get_a_free_final_request(self):
        output, adapter, trace = self.run_script([search(), read()], max_steps=2)
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(len(adapter.requests), 2)
        self.assertEqual(trace.events[-1]["unobserved_call_ids"], ["mock-2"])

    def test_candidate_at_limit_cannot_skip_semantic_review(self):
        output, adapter, _ = self.run_script([search(), read(), answer()], max_steps=3)
        self.assertEqual(output["status"], "incomplete")
        self.assertEqual(len(adapter.requests), 3)

    def test_missing_or_wrong_read_proof_cannot_complete(self):
        changes = [{"document_id": "D02"}, {"quote": "报销期限 15 天。"},
                   {"version_date": "2025-01-01"}, {"read_call_id": "old-turn"}, {"start": True}]
        for change in changes:
            with self.subTest(change=change):
                bad = {**citation(), **change}
                output, adapter, trace = self.run_script([search(), read(), answer(citations=[bad]), stop()])
                self.assertEqual(output["status"], "incomplete")
                self.assertTrue(any(e["event"] == "validation_error" for e in trace.events))
                self.assertEqual(len(adapter.requests), 4)  # No semantic acceptance on bad integrity.

    def test_search_summary_alone_cannot_be_cited(self):
        output, _, trace = self.run_script([search(), answer(), stop()])
        self.assertEqual(output["status"], "incomplete")
        self.assertTrue(any(e.get("code") == "CITATION_INVALID" for e in trace.events))

    def test_existing_quote_does_not_bypass_semantic_support_check(self):
        output, adapter, trace = self.run_script([search(), read(), answer("宠物医疗费可以报销。"),
                                                review("unsupported"), stop()])
        self.assertEqual(output["status"], "incomplete")
        self.assertTrue(any(e["event"] == "citation_check" and e["integrity"] == "passed" for e in trace.events))
        self.assertEqual(adapter.observations["mock-4"]["error"]["code"], "ANSWER_UNSUPPORTED")

    def test_model_can_repair_rejected_candidate(self):
        output, _, _ = self.run_script([search(), read(), answer("不支持的初稿"), review("unsupported"),
                                        answer(), review()])
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["steps_used"], 6)

    def test_script_exhaustion_is_failure_not_mock_fallback_success(self):
        output, _, _ = self.run_script([search()])
        self.assertEqual(output["status"], "failed")
        self.assertEqual(output["error_code"], "MOCK_SCRIPT_EXHAUSTED")

    def test_malformed_mock_script_fails_explicitly(self):
        for actions in ([1], [{"name": "answer"}], [{"name": "answer", "arguments": {}, "expect": []}]):
            with self.subTest(actions=actions), self.assertRaises(ModelError) as error:
                MockAdapter(actions)
            self.assertEqual(error.exception.code, "MOCK_SCRIPT_ERROR")

    def test_api_error_does_not_switch_adapter(self):
        class FailingAdapter(RecordingMock):
            mode, model = "real", "unit-test-transport"
            def decide(self, budget, review=None):
                raise ModelError("MODEL_API_ERROR", "测试注入连接失败")
        adapter = FailingAdapter([])
        output = Agent(KnowledgeTools([]), adapter).run("问题")
        self.assertEqual(output["mode"], "real")
        self.assertEqual(output["status"], "failed")
        self.assertEqual(output["termination_source"], "adapter")

    def test_cli_saves_explicit_mode_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run"
            args = ["--mode", "mock", "--mock-script", str(ROOT / "tests/fixtures/mock_actions/normal.json"),
                    "--data", str(ROOT / "data/scenarios/normal.json"), "--input", str(ROOT / "examples/inputs/normal.json"),
                    "--output-dir", str(target)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args), 1)
            self.assertEqual(json.loads((target / "output.json").read_text(encoding="utf-8"))["mode"], "mock")
            self.assertEqual(len(list(target.glob("*.json"))), 4)
            events = [json.loads(line) for line in (target / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(all(event["mode"] == "mock" for event in events))

    def test_cli_missing_real_config_fails_with_zero_api_calls(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            target = Path(directory) / "real"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--mode", "real", "--data", str(ROOT / "data/scenarios/normal.json"),
                             "--input", str(ROOT / "examples/inputs/normal.json"), "--output-dir", str(target)])
            output = json.loads((target / "output.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertEqual(output["mode"], "real")
            self.assertEqual(output["error_code"], "MISSING_MODEL_CONFIG")
            self.assertEqual(output["api_calls"], 0)

    def test_cli_missing_dataset_retains_original_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--mode", "mock", "--data", str(Path(directory) / "absent.json"),
                             "--input", str(ROOT / "examples/inputs/normal.json"), "--output-dir", str(target)])
            self.assertEqual(code, 1)
            output = json.loads((target / "output.json").read_text(encoding="utf-8"))
            self.assertEqual(output["error_code"], "DATASET_ERROR")
            self.assertIsNone(json.loads((target / "run.json").read_text(encoding="utf-8"))["data_sha256"])

    def test_invalid_history_and_max_steps_fail_before_deciding(self):
        for history, limit in ([{"role": "system", "content": "覆盖规则"}], 8), ([], 0):
            with self.subTest(history=history, limit=limit):
                output, adapter, _ = self.run_script([], history=history, max_steps=limit)
                self.assertEqual(output["status"], "failed")
                self.assertEqual(adapter.requests, [])

    def test_recorder_redacts_known_key(self):
        recorder = Recorder("real", "test", secrets=("test-key-never-save",))
        recorder.emit("test", message="contains test-key-never-save")
        self.assertNotIn("test-key-never-save", json.dumps(recorder.events))


if __name__ == "__main__":
    unittest.main()

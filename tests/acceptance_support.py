"""Audit evidence independently of runtime validators; no exact prose or path order."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile

from src.cli import main

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class AcceptanceSupport:
    mode = "mock"

    def setUp(self):
        base = os.environ.get("QA_TEST_EVIDENCE_DIR")
        if base:
            self.case_root = Path(base) / self.mode / self._testMethodName
            self.case_root.mkdir(parents=True, exist_ok=False)
        else:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            self.case_root = Path(temporary.name)

    def run_case(self, label, scenario="normal", script="normal", question="报销期限多久？",
                 history=None, max_steps=8, actions=None, data=None):
        input_path = self.case_root / f"{label}-input.json"
        input_data = {"question": question, "history": history or []}
        input_path.write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
        data_path = ROOT / "data/scenarios" / f"{scenario}.json"
        if data is not None:
            data_path = self.case_root / f"{label}-data.json"
            data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        folder = self.case_root / label
        args = ["--mode", self.mode, "--data", str(data_path), "--input", str(input_path),
                "--max-steps", str(max_steps), "--output-dir", str(folder)]
        if self.mode == "mock":
            script_path = ROOT / "tests/fixtures/mock_actions" / f"{script}.json"
            if actions is not None:
                script_path = self.case_root / f"{label}-actions.json"
                script_path.write_text(json.dumps({"mode": "mock", "actions": actions}, ensure_ascii=False), encoding="utf-8")
            args += ["--mock-script", str(script_path)]
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = main(args)
        bundle = {name: read_json(folder / f"{name}.json") for name in ("input", "output", "documents", "run")}
        bundle["trace"] = [json.loads(line) for line in (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        bundle["folder"], bundle["exit_code"] = folder, exit_code
        if os.environ.get("QA_TEST_EVIDENCE_DIR"):
            index = Path(os.environ["QA_TEST_EVIDENCE_DIR"]).parent / "case-runs.jsonl"
            record = {"test_id": self.id(), "label": label, "mode": self.mode,
                      "evidence": folder.relative_to(index.parent).as_posix(),
                      "actual_status": bundle["output"]["status"], "exit_code": exit_code,
                      "api_calls": bundle["output"]["api_calls"]}
            with index.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.audit_bundle(bundle)
        return bundle

    def audit_bundle(self, bundle):
        output, events, run = bundle["output"], bundle["trace"], bundle["run"]
        self.assertEqual(output["mode"], self.mode)
        self.assertEqual(run["mode"], self.mode)
        self.assertTrue(events)
        self.assertTrue(all(event["mode"] == self.mode for event in events))
        self.assertEqual(events[-1]["event"], "run_finished")
        self.assertEqual(events[-1]["status"], output["status"])
        self.assertEqual(output["steps_used"], run["steps_used"])
        self.assertLessEqual(output["steps_used"], run["max_steps"])
        self.assertEqual(bundle["exit_code"], {"completed": 0, "needs_clarification": 0,
                         "incomplete": 2, "failed": 1}[output["status"]])
        if self.mode == "mock":
            self.assertEqual(output["api_calls"], 0)
        documents = {document["id"]: document for document in bundle["documents"]["documents"]}
        reads = {event["call_id"]: event["result"]["data"] for event in events
                 if event["event"] == "tool_result" and event["tool"] == "read_document"
                 and event["result"]["ok"]}
        for cite in output["citations"]:
            self.assertIn(cite["document_id"], documents)
            document = documents[cite["document_id"]]
            self.assertEqual(cite["version_date"], document["version_date"])
            self.assertEqual(type(cite["start"]), int)
            self.assertEqual(type(cite["end"]), int)
            self.assertLess(cite["start"], cite["end"])
            self.assertEqual(document["content"][cite["start"]:cite["end"]], cite["quote"])
            self.assertIn(cite["read_call_id"], reads)
            observed = reads[cite["read_call_id"]]
            self.assertEqual(cite["document_id"], observed["id"])
            self.assertGreaterEqual(cite["start"], observed["start"])
            self.assertLessEqual(cite["end"], observed["end"])
        if output["status"] == "completed":
            self.assertTrue(output["citations"])
            self.assertEqual(output["gaps"], [])
            self.assertEqual(output["verification"]["citation_integrity"], "passed")
            self.assertEqual(output["verification"]["semantic_support"]["verdict"], "supported")
            self.assertEqual(output["verification"]["semantic_support"]["mode"], self.mode)
        else:
            self.assertTrue(output["gaps"])
            self.assertTrue(all(isinstance(gap, str) and gap.strip() for gap in output["gaps"]))

    def check_deadline(self, bundle):
        output = bundle["output"]
        self.assertEqual(output["status"], "completed")
        # Accept digits/Chinese numerals, day/date wording and arbitrary full sentences.
        self.assertRegex(output["answer"], r"(?:30|三十)\s*(?:个)?\s*(?:自然|日历)?\s*[天日]")
        self.assertTrue(any(cite["document_id"] == "D01" and "30" in cite["quote"]
                            for cite in output["citations"]))

    def check_conflict(self, bundle):
        output = bundle["output"]
        self.assertEqual(output["status"], "needs_clarification")
        quotes = {cite["document_id"]: cite["quote"] for cite in output["citations"]}
        self.assertIn("30", quotes.get("D01", ""))
        self.assertIn("15", quotes.get("D02", ""))
        text = output["answer"] + " ".join(output["gaps"])
        self.assertRegex(text, r"适用|范围|优先|制度")
        self.assertRegex(output["answer"], r"请|确认|提供|说明|[?？]")
        # No check against an exact sequence or number of search/read calls.

    def check_tool_failure(self, bundle):
        output = bundle["output"]
        self.assertIn(output["status"], ("failed", "incomplete"))
        self.assertEqual(output["citations"], [])
        errors = [event["result"]["error"]["code"] for event in bundle["trace"]
                  if event["event"] == "tool_result" and not event["result"]["ok"]]
        self.assertIn("TOOL_UNAVAILABLE", errors)
        self.assertRegex(output["answer"] + " ".join(output["gaps"]), r"故障|读取失败|不可用|工具.*失败|工具.*恢复")


class BusinessChecks(AcceptanceSupport):
    def test_b01_clear_answer(self):
        self.check_deadline(self.run_case("normal"))

    def test_b02_conflicting_documents(self):
        self.check_conflict(self.run_case("conflict", scenario="conflict", script="conflict"))

    def test_b03_outside_corpus_with_partial_keyword_hits(self):
        bundle = self.run_case("outside", scenario="normal", script="out_of_scope",
                               question="公司是否报销宠物医疗费？")
        self.assertIn(bundle["output"]["status"], ("incomplete", "needs_clarification"))
        self.assertTrue(bundle["output"]["gaps"])
        if self.mode == "mock":
            self.assertTrue(any(event["event"] == "tool_result" and event["tool"] == "search_documents"
                                and event["result"]["ok"] and event["result"]["data"]["matches"]
                                for event in bundle["trace"]))

    def test_b04_paraphrase_preserves_facts_and_sources(self):
        first = self.run_case("original")
        second = self.run_case("paraphrase", script="paraphrase", question="费用报销最迟得在多少天内办？")
        self.check_deadline(first)
        self.check_deadline(second)
        # Each case is independent; compare facts, not full strings or action order.

    def test_b05_context_follow_up(self):
        first = self.run_case("first", question="差旅报销期限多久？")
        # Context resolution does not require the first turn to overstate scope.
        # D01 gives a deadline without explicitly naming travel; a cautious first
        # answer may keep that gap. Preserve its actual wording in the next input.
        self.assertIn(first["output"]["status"], ("completed", "incomplete", "needs_clarification"))
        self.assertTrue(any(cite["document_id"] == "D01" and "30" in cite["quote"]
                            for cite in first["output"]["citations"]))
        history = [{"role": "user", "content": "差旅报销期限多久？"},
                   {"role": "assistant", "content": first["output"]["answer"]}]
        second = self.run_case("follow-up", script="follow_up", question="那需要什么材料？", history=history)
        self.assertEqual(second["input"]["history"], history)
        self.assertEqual(second["output"]["status"], "completed")
        quotes = " ".join(cite["quote"] for cite in second["output"]["citations"] if cite["document_id"] == "D03")
        self.assertIn("发票", quotes)
        self.assertIn("出差审批单", quotes)

    def test_b06_tool_failure_has_explicit_cause(self):
        self.check_tool_failure(self.run_case("failure", scenario="tool_error", script="tool_error"))

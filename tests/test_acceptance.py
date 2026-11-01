"""Business outcomes and adversarial boundaries, using only offline scripts."""

import unittest

from src.agent import Agent, Recorder
from src.models import TranscriptAdapter
from src.tools import KnowledgeTools
from tests.acceptance_support import AcceptanceSupport, BusinessChecks
from tests.test_agent import RecordingMock, action, answer, citation, read, review, search, stop


class OfflineAcceptanceTests(BusinessChecks, unittest.TestCase):
    pass


class BoundaryAcceptanceTests(AcceptanceSupport, unittest.TestCase):
    def test_x01_underspecified_question_asks_specific_field(self):
        bundle = self.run_case("ambiguous", scenario="ambiguous", script="ambiguous", question="多久？")
        output = bundle["output"]
        self.assertEqual(output["status"], "needs_clarification")
        self.assertRegex(output["answer"], r"事项|制度|主题|业务")
        self.assertRegex(" ".join(output["gaps"]), r"事项|制度|主题|业务")

    def test_x02_execution_limit_is_explicitly_incomplete(self):
        bundle = self.run_case("limit", max_steps=2)
        self.assertEqual(bundle["output"]["status"], "incomplete")
        self.assertEqual(bundle["output"]["error_code"], "EXECUTION_LIMIT")
        self.assertEqual(bundle["output"]["steps_used"], 2)
        self.assertTrue(bundle["trace"][-1]["unobserved_call_ids"])

    def test_x03_nonexistent_id_and_wrong_quote_cannot_complete(self):
        for label, change in (("unknown-id", {"document_id": "D999"}),
                              ("wrong-quote", {"quote": "报销期限 15 天。"})):
            with self.subTest(label=label):
                bad = {**citation(), **change}
                bundle = self.run_case(label, actions=[search(), read(), answer(citations=[bad]), stop()])
                self.assertNotEqual(bundle["output"]["status"], "completed")
                self.assertTrue(any(event.get("code") == "CITATION_INVALID" for event in bundle["trace"]))

    def test_x04_failed_read_cannot_be_reported_as_success(self):
        attempted = answer()
        attempted["expect"] = {"mock-2": {"ok": False, "error": {"code": "TOOL_UNAVAILABLE"}}}
        final = stop("failed")
        final["expect"] = {"mock-3": {"ok": False, "error": {"code": "CITATION_INVALID"}}}
        bundle = self.run_case("fake-success", scenario="tool_error", actions=[search(), read(), attempted, final])
        self.assertEqual(bundle["output"]["status"], "failed")
        self.assertFalse(any(event["event"] == "answer_review" for event in bundle["trace"]))

    def test_x05_existing_quote_does_not_prove_support(self):
        bundle = self.run_case("unsupported", script="unsupported_answer")
        self.assertEqual(bundle["output"]["status"], "incomplete")
        self.assertTrue(any(event["event"] == "citation_check" and event["integrity"] == "passed" for event in bundle["trace"]))
        self.assertTrue(any(event["event"] == "answer_review" and event["verdict"] == "unsupported" for event in bundle["trace"]))

    def test_x06_different_wording_and_valid_action_order_are_accepted(self):
        first = self.run_case("standard")
        altered = [read(), search(), answer("最迟应在三十日内办理。", [citation(call_id="mock-1")]), review()]
        second = self.run_case("other-order", actions=altered)
        self.check_deadline(first)
        self.check_deadline(second)
        self.assertNotEqual(first["output"]["answer"], second["output"]["answer"])
        self.assertNotEqual([e["action"] for e in first["trace"] if e["event"] == "model_action"],
                            [e["action"] for e in second["trace"] if e["event"] == "model_action"])

    def test_x07_partial_read_cannot_cite_unread_source_text(self):
        partial = action("read_document", document_id="D01", start=0, length=4)
        bundle = self.run_case("unread-tail", actions=[search(), partial, answer(), stop()])
        self.assertEqual(bundle["output"]["status"], "incomplete")
        self.assertTrue(any(e.get("code") == "CITATION_INVALID" for e in bundle["trace"]))

    def test_x08_nonzero_offsets_and_subquotes_are_valid(self):
        data = {"documents": [{"id": "D01", "title": "报销期限", "version_date": "2026-10-01",
                               "content": "说明：\n报销期限 30 天。\n其余内容。"}]}
        raw = data["documents"][0]["content"]
        start = raw.index("报销")
        end = raw.index("。", start) + 1
        selected = {**citation(), "start": start, "end": end}
        actions = [search(), action("read_document", document_id="D01", start=start, length=end-start),
                   answer(citations=[selected]), review()]
        self.check_deadline(self.run_case("offset", actions=actions, data=data))

    def test_x09_read_failure_can_recover_only_after_new_model_action(self):
        class TransientTools(KnowledgeTools):
            def __init__(self):
                super().__init__([{"id": "D01", "title": "报销期限", "version_date": "2026-10-01", "content": "报销期限 30 天。"}])
                self.reads = 0
            def read_document(self, *args, **kwargs):
                self.reads += 1
                if self.reads == 1:
                    return {"ok": False, "error": {"code": "TOOL_UNAVAILABLE", "message": "暂时读取失败", "retryable": True}}
                return super().read_document(*args, **kwargs)
        retry = read()
        retry["expect"] = {"mock-2": {"ok": False}}
        adapter = RecordingMock([search(), read(), retry, answer(citations=[citation(call_id="mock-3")]), review()])
        recorder = Recorder("mock", adapter.model)
        tools = TransientTools()
        result = Agent(tools, adapter, recorder).run("报销期限多久？")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(tools.reads, 2)
        self.assertEqual(adapter.requests[2]["items"][-1]["call_id"], "mock-2")
        self.assertEqual(result["citations"][0]["read_call_id"], "mock-3")

    def test_x10_empty_model_responses_cannot_loop_forever(self):
        class EmptyAdapter(TranscriptAdapter):
            mode, model = "mock", "empty-response-test"
            def decide(self, budget, review=None):
                return {"calls": []}
        recorder = Recorder("mock", "empty-response-test")
        result = Agent(KnowledgeTools([]), EmptyAdapter(), recorder).run("问题", max_steps=3)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["steps_used"], 3)
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(sum(e["event"] == "validation_error" for e in recorder.events), 3)

    def test_x11_duplicate_call_id_does_not_overwrite_evidence(self):
        first, second = search(), read()
        first["call_id"] = second["call_id"] = "duplicate"
        adapter = RecordingMock([first, second])
        result = Agent(KnowledgeTools([]), adapter).run("问题")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "MODEL_PROTOCOL_ERROR")


if __name__ == "__main__":
    unittest.main()

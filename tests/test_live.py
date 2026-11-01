"""Real-model acceptance. Explicit opt-in AND local credentials are required."""

import os
import unittest

from tests.acceptance_support import AcceptanceSupport, BusinessChecks, ROOT, read_json


LIVE_ENABLED = (os.environ.get("QA_LIVE_VALIDATE") == "1"
                and bool(os.environ.get("DEEPSEEK_API_KEY")) and bool(os.environ.get("DEEPSEEK_MODEL")))


@unittest.skipUnless(LIVE_ENABLED, "未运行：需显式 --live 及本机模型配置；Mock 不能替代")
class LiveAcceptanceTests(BusinessChecks, unittest.TestCase):
    mode = "real"


@unittest.skipUnless(LIVE_ENABLED, "未运行：需显式 --live 及本机模型配置；Mock 不能替代")
class LiveBoundaryTests(AcceptanceSupport, unittest.TestCase):
    mode = "real"

    def test_conflict_content_change(self):
        data = read_json(ROOT / "data/scenarios/conflict.json")
        d02 = next(document for document in data["documents"] if document["id"] == "D02")
        self.assertEqual(d02["content"], "报销期限 15 天。")
        d02["content"] = "报销期限 30 天。"
        bundle = self.run_case("same-deadline", data=data)
        self.assertEqual(bundle["output"]["status"], "completed")
        self.assertRegex(bundle["output"]["answer"], r"(?:30|三十)\s*[天日]")
        self.assertTrue(any(cite["document_id"] in ("D01", "D02") and "30" in cite["quote"]
                            for cite in bundle["output"]["citations"]))

    def test_underspecified_question(self):
        bundle = self.run_case("ambiguous", scenario="ambiguous", question="多久？")
        self.assertEqual(bundle["output"]["status"], "needs_clarification")
        self.assertRegex(bundle["output"]["answer"], r"事项|制度|主题|业务|报销|请假")
        self.assertTrue(bundle["output"]["gaps"])

    def test_execution_limit(self):
        bundle = self.run_case("limit", max_steps=1)
        self.assertEqual(bundle["output"]["status"], "incomplete")
        self.assertEqual(bundle["output"]["error_code"], "EXECUTION_LIMIT")
        self.assertEqual(bundle["output"]["steps_used"], 1)

    def test_no_related_documents(self):
        bundle = self.run_case("no-match", scenario="no_match")
        self.assertIn(bundle["output"]["status"], ("incomplete", "needs_clarification"))
        self.assertEqual(bundle["output"]["citations"], [])
        self.assertTrue(any(event["event"] == "tool_result"
                            and event["tool"] == "search_documents"
                            and event["result"]["ok"]
                            and not event["result"]["data"]["matches"]
                            for event in bundle["trace"]))


@unittest.skipUnless(LIVE_ENABLED, "未运行：需显式 --live 及本机模型配置；Mock 不能替代")
class LiveSynonymTests(AcceptanceSupport, unittest.TestCase):
    mode = "real"

    def test_conflict_with_synonym_question(self):
        self.check_conflict(self.run_case("conflict", scenario="conflict", question="报销时效有多久？"))

    def test_agreement_with_synonym_question(self):
        data = read_json(ROOT / "data/scenarios/conflict.json")
        document = next(item for item in data["documents"] if item["id"] == "D02")
        self.assertEqual(document["content"], "报销期限 15 天。")
        document["content"] = "报销期限 30 天。"
        bundle = self.run_case("agreement", data=data, question="报销时效有多久？")
        self.assertEqual(bundle["output"]["status"], "completed")
        self.assertRegex(bundle["output"]["answer"], r"(?:30|三十)\s*[天日]")
        self.assertTrue(any(cite["document_id"] in ("D01", "D02") and "30" in cite["quote"]
                            for cite in bundle["output"]["citations"]))


if __name__ == "__main__":
    unittest.main()

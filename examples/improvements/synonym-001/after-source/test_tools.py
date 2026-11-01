"""Tool-only checks. These do not run a real or Mock model or any Agent loop."""

import json
import tempfile
import unittest
from pathlib import Path

from src.tools import DatasetError, KnowledgeTools


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "data" / "scenarios"


class ToolTests(unittest.TestCase):
    def load(self, name="normal"):
        return KnowledgeTools.from_file(SCENARIOS / f"{name}.json")

    def assert_error(self, result, code):
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], code)
        self.assertNotIn("data", result)
        self.assertNotIn("matches", result)

    def test_normal_search_metadata_and_verbatim_read(self):
        tools = self.load()
        match = tools.search_documents("报销期限多久？")["data"]["matches"][0]
        self.assertEqual(match["id"], "D01")
        self.assertEqual(match["version_date"], "2026-10-01")
        fragment = tools.read_document(match["id"])["data"]
        self.assertEqual(fragment["text"], "报销期限 30 天。")
        self.assertEqual(fragment["version_date"], match["version_date"])
        self.assertFalse(fragment["has_more"])

    def test_synonym_queries_retrieve_same_evidence(self):
        for query in ("报销期限多久？", "费用报销最迟得在多少天内办？", "报账时限是几天？"):
            with self.subTest(query=query):
                result = self.load().search_documents(query)
                self.assertTrue(result["ok"])
                self.assertEqual(result["data"]["matches"][0]["id"], "D01")

    def test_material_synonym_retrieves_document(self):
        result = self.load().search_documents("差旅报销需要哪些凭证？")
        self.assertEqual(result["data"]["matches"][0]["id"], "D03")

    def test_reimbursement_validity_synonym_prefers_deadline(self):
        tools = self.load()
        matches = tools.search_documents("报销时效有多久？")["data"]["matches"]
        self.assertEqual(matches[0]["id"], "D01")
        scores = {match["id"]: match["score"] for match in matches}
        self.assertGreater(scores["D01"], scores["D03"])

    def test_validity_synonym_keeps_conflicts_and_original_text(self):
        tools = self.load("conflict")
        before = tools.snapshot()
        matches = tools.search_documents("报销时效有多久？")["data"]["matches"]
        self.assertEqual({match["id"] for match in matches}, {"D01", "D02"})
        self.assertEqual({match["id"]: match["version_date"] for match in matches},
                         {"D01": "2026-10-01", "D02": "2026-10-15"})
        for document in before["documents"]:
            fragment = tools.read_document(document["id"])["data"]
            self.assertEqual(fragment["text"], document["content"])
            self.assertEqual(fragment["text"], document["content"][fragment["start"]:fragment["end"]])
        self.assertEqual(tools.snapshot(), before)

    def test_conflicting_documents_both_remain_visible(self):
        tools = self.load("conflict")
        matches = tools.search_documents("报销期限")["data"]["matches"]
        self.assertEqual([match["id"] for match in matches], ["D01", "D02"])
        self.assertEqual(tools.read_document("D01")["data"]["text"], "报销期限 30 天。")
        self.assertEqual(tools.read_document("D02")["data"]["text"], "报销期限 15 天。")
        raw = json.loads((SCENARIOS / "conflict.json").read_text(encoding="utf-8"))
        for document in raw["documents"]:
            self.assertNotIn("scope", document)
            self.assertNotIn("priority", document)

    def test_limit_exposes_truncation_instead_of_hiding_other_match(self):
        data = self.load("conflict").search_documents("报销期限", limit=1)["data"]
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["total_matches"], 2)
        self.assertTrue(data["has_more"])

    def test_unrelated_corpus_is_successful_zero_match(self):
        result = self.load("no_match").search_documents("报销期限多久？")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["matches"], [])
        self.assertEqual(result["data"]["total_matches"], 0)

    def test_underspecified_query_does_not_invent_a_topic_or_action(self):
        result = self.load("ambiguous").search_documents("多久？")
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["matches"], [])
        self.assertEqual(set(result["data"]), {"query", "matches", "total_matches", "has_more"})

    def test_read_fault_is_persistent_explicit_and_search_still_works(self):
        tools = self.load("tool_error")
        self.assertEqual(tools.search_documents("报销期限")["data"]["matches"][0]["id"], "D01")
        for _ in range(2):
            self.assert_error(tools.read_document("D01"), "TOOL_UNAVAILABLE")
        self.assertTrue(self.load().read_document("D01")["ok"])

    def test_search_fault_is_not_zero_matches(self):
        tools = KnowledgeTools([], {"search_documents": True})
        self.assert_error(tools.search_documents("报销期限"), "TOOL_UNAVAILABLE")

    def test_scenarios_do_not_leak_documents_between_instances(self):
        normal, conflict = self.load(), self.load("conflict")
        self.assert_error(normal.read_document("D02"), "DOCUMENT_NOT_FOUND")
        self.assertTrue(conflict.read_document("D02")["ok"])
        self.assert_error(normal.read_document("D02"), "DOCUMENT_NOT_FOUND")

    def test_dataset_changes_and_filename_do_not_select_answers(self):
        payload = json.loads((SCENARIOS / "normal.json").read_text(encoding="utf-8"))
        payload["documents"][0]["content"] = "报销期限 45 天。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tool_error.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tools = KnowledgeTools.from_file(path)
            self.assertEqual(tools.read_document("D01")["data"]["text"], "报销期限 45 天。")
            self.assertIn("45", tools.search_documents("报销期限")["data"]["matches"][0]["summary"])

    def test_fault_comes_from_config_not_filename(self):
        payload = json.loads((SCENARIOS / "tool_error.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normal.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assert_error(KnowledgeTools.from_file(path).read_document("D01"), "TOOL_UNAVAILABLE")

    def test_unicode_slice_is_exact_and_search_does_not_normalize_source(self):
        source = "第一行。\n报销期限 ３０ 天。\n🙂原文保持　全角空格。"
        tools = KnowledgeTools([{
            "id": "D20", "title": "报销期限", "version_date": "2026-10-01", "content": source,
        }])
        self.assertTrue(tools.search_documents("报销期限30天")["ok"])
        data = tools.read_document("D20", start=5, length=10)["data"]
        self.assertEqual(data["text"], "报销期限 ３０ 天。")
        self.assertEqual(source[data["start"]:data["end"]], data["text"])
        self.assertTrue(data["has_more"])
        self.assertEqual(tools.read_document("D20")["data"]["text"], source)

    def test_read_continuation_reconstructs_original(self):
        tools = self.load()
        first = tools.read_document("D01", length=4)["data"]
        second = tools.read_document("D01", start=first["end"])["data"]
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertEqual(first["text"] + second["text"], "报销期限 30 天。")

    def test_search_rejects_invalid_arguments(self):
        tools = self.load()
        for query in ("", "  ", None, 123):
            with self.subTest(query=query):
                self.assert_error(tools.search_documents(query), "INVALID_ARGUMENT")
        for limit in (0, 21, True, "5"):
            with self.subTest(limit=limit):
                self.assert_error(tools.search_documents("报销", limit), "INVALID_ARGUMENT")

    def test_read_rejects_missing_ids_and_invalid_ranges(self):
        tools = self.load()
        self.assert_error(tools.read_document("D99"), "DOCUMENT_NOT_FOUND")
        for document_id in ("", None, 12):
            with self.subTest(document_id=document_id):
                self.assert_error(tools.read_document(document_id), "INVALID_ARGUMENT")
        for arguments in ({"start": -1}, {"start": 999}, {"start": True},
                          {"length": 0}, {"length": 2001}, {"length": "2"}):
            with self.subTest(arguments=arguments):
                self.assert_error(tools.read_document("D01", **arguments), "INVALID_ARGUMENT")

    def test_invalid_dataset_is_not_an_empty_index(self):
        document = {"id": "D01", "title": "报销期限", "version_date": "2026-10-01", "content": "原文"}
        for documents in (None, [{"id": "D01"}], [dict(document, version_date="2026-02-30")],
                          [document, document], [dict(document, content=" ")]):
            with self.subTest(documents=documents), self.assertRaises(DatasetError):
                KnowledgeTools(documents)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            with self.assertRaises(DatasetError):
                KnowledgeTools.from_file(path)
            for raw in ("{invalid json", '[]', '{}', '{"documents": [], "next_action": "answer"}',
                        '{"documents": [], "faults": null}', '{"documents": [], "faults": []}'):
                with self.subTest(raw=raw):
                    path.write_text(raw, encoding="utf-8")
                    with self.assertRaises(DatasetError):
                        KnowledgeTools.from_file(path)

    def test_snapshot_copies_input_and_rejects_action_fault_config(self):
        document = {"id": "D01", "title": "报销期限", "version_date": "2026-10-01", "content": "报销期限 30 天。"}
        tools = KnowledgeTools([document])
        document["content"] = "已被外部修改"
        self.assertEqual(tools.read_document("D01")["data"]["text"], "报销期限 30 天。")
        for faults in ({"next_action": True}, {"read_document": "answer"}):
            with self.subTest(faults=faults), self.assertRaises(DatasetError):
                KnowledgeTools([], faults)

    def test_optional_scope_must_be_actual_source_text(self):
        document = {"id": "D20", "title": "差旅期限", "version_date": "2026-10-01",
                    "content": "仅适用于境内差旅。报销期限 30 天。", "scope": "仅适用于境内差旅。"}
        tools = KnowledgeTools([document])
        self.assertEqual(tools.read_document("D20")["data"]["scope"], document["scope"])
        self.assertEqual(tools.search_documents("差旅期限")["data"]["matches"][0]["scope"], document["scope"])
        with self.assertRaises(DatasetError):
            KnowledgeTools([{**document, "scope": "适用于所有员工"}])

    def test_snapshot_does_not_allow_mutating_live_documents(self):
        tools = self.load()
        snapshot = tools.snapshot()
        snapshot["documents"][0]["content"] = "externally changed"
        self.assertEqual(tools.read_document("D01")["data"]["text"], "报销期限 30 天。")


if __name__ == "__main__":
    unittest.main()

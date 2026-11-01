"""Responses protocol unit tests with in-memory HTTP responses; zero network."""

import copy
import json
import unittest
from unittest.mock import patch
import urllib.error

from src.models import DeepSeekResponsesAdapter, ModelError


class ModelTests(unittest.TestCase):
    def test_actual_observation_and_history_are_in_next_http_payload(self):
        requests = []
        def transport(payload):
            requests.append(copy.deepcopy(payload))
            return {"status": "completed", "id": f"r{len(requests)}", "model": "unit-test-model", "output": [
                {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "unit-test-continuation-only"}]},
                {"type": "function_call", "call_id": f"c{len(requests)}", "name": "search_documents",
                 "arguments": '{"query":"x","limit":5,"decision_summary":"test"}'}]}
        adapter = DeepSeekResponsesAdapter("public-unit-test-key", "unit-test-model", transport=transport)
        history = [{"role": "user", "content": "previous question"}, {"role": "assistant", "content": "previous answer"}]
        adapter.start("new question", history)
        adapter.decide({"remaining": 7})
        observation = {"ok": False, "error": {"code": "TOOL_UNAVAILABLE", "message": "injected"}}
        adapter.observe("c1", observation)
        adapter.decide({"remaining": 6})
        self.assertEqual(requests[1]["input"][:2], history)
        observed = requests[1]["input"][-1]
        self.assertEqual(observed["call_id"], "c1")
        self.assertEqual(json.loads(observed["output"]), observation)
        self.assertIn('"remaining": 6', requests[1]["instructions"])
        self.assertEqual(requests[1]["reasoning"], {"effort": "none"})
        self.assertNotIn("store", requests[1])
        self.assertNotIn("include", requests[1])
        self.assertNotIn("parallel_tool_calls", requests[1])
        self.assertTrue(all("strict" not in tool for tool in requests[1]["tools"]))
        self.assertTrue(any(item.get("type") == "reasoning" for item in requests[1]["input"]))

    def test_review_uses_same_provider_and_separate_function(self):
        requests = []
        def transport(payload):
            requests.append(payload)
            return {"status": "completed", "output": [{"type": "function_call", "call_id": "r1", "name": "assess_answer",
                                                         "arguments": '{"verdict":"unsupported","reason":"test"}'}]}
        adapter = DeepSeekResponsesAdapter("public-test-key", "unit-test-model", transport=transport)
        adapter.start("question", [])
        adapter.decide({"remaining": 4}, review={"answer": "candidate"})
        self.assertEqual(requests[0]["tools"][0]["name"], "assess_answer")
        self.assertIn("candidate", requests[0]["input"][-1]["content"])

    def test_incomplete_response_cannot_be_accepted(self):
        adapter = DeepSeekResponsesAdapter("public-test-key", "unit-test-model", transport=lambda p: {"status": "incomplete"})
        adapter.start("question", [])
        with self.assertRaises(ModelError) as error:
            adapter.decide({})
        self.assertEqual(error.exception.code, "MODEL_RESPONSE_INCOMPLETE")

    def test_http_error_is_sanitized_without_hidden_retry(self):
        adapter = DeepSeekResponsesAdapter("public-test-key", "unit-test-model")
        adapter.start("question", [])
        with patch("urllib.request.OpenerDirector.open", side_effect=urllib.error.HTTPError(
                adapter.ENDPOINT, 401, "untrusted body public-test-key", {}, None)) as request:
            with self.assertRaises(ModelError) as error:
                adapter.decide({})
        self.assertEqual(request.call_count, 1)
        self.assertNotIn("public-test-key", str(error.exception))
        self.assertEqual(error.exception.code, "MODEL_API_ERROR")

    def test_missing_config_does_not_attempt_transport(self):
        with self.assertRaises(ModelError):
            DeepSeekResponsesAdapter("", "")


if __name__ == "__main__":
    unittest.main()

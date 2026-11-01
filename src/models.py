"""One real provider. HTTP transport can be replaced ONLY by unit tests.

Protocol sources (checked 2026-11-01):
https://api-docs.deepseek.com/guides/responses_api/
https://api-docs.deepseek.com/guides/tool_calls/
"""

from __future__ import annotations

import copy
import json
import socket
import urllib.error
import urllib.request

from src.prompts import INSTRUCTIONS, REVIEW_DEFINITION, REVIEW_INSTRUCTIONS, TOOL_DEFINITIONS


class ModelError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class TranscriptAdapter:
    mode = "undefined"
    model = "undefined"
    api_calls = 0

    def start(self, question, history):
        self.items = copy.deepcopy(history) + [{"role": "user", "content": question}]

    def observe(self, call_id, result):
        self.items.append({"type": "function_call_output", "call_id": call_id,
                           "output": json.dumps(result, ensure_ascii=False)})

    def feedback(self, message):
        self.items.append({"role": "developer", "content": message})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirect destination.


class DeepSeekResponsesAdapter(TranscriptAdapter):
    mode = "real"
    ENDPOINT = "https://api.deepseek.com/responses"

    def __init__(self, api_key, model, timeout=30, *, transport=None):
        if not api_key or not model:
            raise ModelError("MISSING_MODEL_CONFIG", "真实模式需要 DEEPSEEK_API_KEY 和 DEEPSEEK_MODEL；未切换 Mock")
        self._key, self.model, self.timeout = api_key, model, timeout
        self._transport = transport or self._post
        self.api_calls = 0

    def _post(self, payload):
        request = urllib.request.Request(
            self.ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self._key, "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not echo untrusted HTTP bodies/headers or the request key.
            raise ModelError("MODEL_API_ERROR", f"DeepSeek HTTP {exc.code}；未降级或自动重试") from None
        except (urllib.error.URLError, OSError, socket.timeout):
            raise ModelError("MODEL_API_ERROR", "DeepSeek 连接失败或超时；未降级或自动重试") from None
        except (ValueError, UnicodeError):
            raise ModelError("MODEL_PROTOCOL_ERROR", "模型服务返回了无效 JSON") from None

    def decide(self, budget, review=None):
        instructions = INSTRUCTIONS + "\n剩余额度：" + json.dumps(budget)
        if review is not None:
            instructions += "\n" + REVIEW_INSTRUCTIONS
        # DeepSeek ignores parallel_tool_calls, store and include. The runner
        # enforces one action and validates schemas instead of assuming strictness.
        definitions = [REVIEW_DEFINITION] if review is not None else TOOL_DEFINITIONS
        payload = {
            "model": self.model, "input": copy.deepcopy(self.items),
            "instructions": instructions,
            "reasoning": {"effort": "none"},
            "tools": [{key: value for key, value in definition.items() if key != "strict"}
                      for definition in definitions],
            "tool_choice": "required",
            "max_output_tokens": 3000,
        }
        if review is not None:
            payload["input"].append({"role": "developer", "content":
                "待复核候选（只按已有证据判断）：" + json.dumps(review, ensure_ascii=False)})
        self.api_calls += 1
        response = self._transport(payload)
        if not isinstance(response, dict) or response.get("status") != "completed":
            raise ModelError("MODEL_RESPONSE_INCOMPLETE", "模型响应未完整结束，未接受为有效决定")
        output = response.get("output")
        if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
            raise ModelError("MODEL_PROTOCOL_ERROR", "模型响应缺少合法 output 列表")
        # Keep protocol continuation in memory only, never internal reasoning in Trace.
        self.items.extend(copy.deepcopy(output))
        self.model = response.get("model") or self.model
        calls = [copy.deepcopy(item) for item in output if item.get("type") == "function_call"]
        return {"calls": calls, "response_id": response.get("id")}

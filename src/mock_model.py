"""Offline scripted adapter; never evidence of genuine model decisions."""

import copy
import json
from pathlib import Path

from src.models import ModelError, TranscriptAdapter


def _contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value) for key, value in expected.items())
    return actual == expected


class MockAdapter(TranscriptAdapter):
    mode = "mock"
    model = "mock-script-v1"
    api_calls = 0

    def __init__(self, actions):
        if not isinstance(actions, list):
            raise ModelError("MOCK_SCRIPT_ERROR", "Mock actions 必须是列表")
        if any(not isinstance(action, dict) or not {"name", "arguments"} <= set(action)
               or not isinstance(action.get("expect", {}), dict) for action in actions):
            raise ModelError("MOCK_SCRIPT_ERROR", "每个 Mock 动作必须有 name/arguments，expect 必须为映射")
        self.actions, self.position = copy.deepcopy(actions), 0
        self.observations = {}

    @classmethod
    def from_file(cls, path):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(payload["actions"])
        except (OSError, ValueError, KeyError, TypeError):
            raise ModelError("MOCK_SCRIPT_ERROR", "无法读取合法 Mock 脚本") from None

    def observe(self, call_id, result):
        super().observe(call_id, result)
        self.observations[call_id] = copy.deepcopy(result)

    def decide(self, budget, review=None):
        if self.position >= len(self.actions):
            raise ModelError("MOCK_SCRIPT_EXHAUSTED", "Mock 脚本结束，未补造成功答案")
        action = copy.deepcopy(self.actions[self.position])
        self.position += 1
        for call_id, expected in action.get("expect", {}).items():
            if not _contains(self.observations.get(call_id), expected):
                raise ModelError("MOCK_OBSERVATION_MISMATCH", "Mock 未收到脚本要求的实际观察")
        if bool(review is not None) != (action.get("name") == "assess_answer"):
            raise ModelError("MOCK_SCRIPT_ERROR", "Mock 动作与当前决策/复核阶段不符")
        call = {"type": "function_call", "call_id": action.get("call_id", f"mock-{self.position}"),
                "name": action.get("name"), "arguments": json.dumps(action.get("arguments"), ensure_ascii=False)}
        self.items.append(copy.deepcopy(call))
        return {"calls": [call], "response_id": f"mock-response-{self.position}"}

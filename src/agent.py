"""Bounded model loop. Business next actions always come from the adapter."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timedelta, timezone

from src.models import ModelError
from src.validation import ValidationError, validate_action, validate_final, validate_input


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class Recorder:
    def __init__(self, mode, model, path=None, secrets=()):
        self.mode, self.model = mode, model
        self.run_id = str(uuid.uuid4())
        self.events, self.path = [], path
        self.secrets = [secret for secret in secrets if secret]

    def clean(self, value):
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {key: self.clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        return value

    def emit(self, event, **fields):
        record = self.clean({"event": event, "run_id": self.run_id, "mode": self.mode,
                             "model": self.model, "time": now(), **fields})
        self.events.append(record)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def failure_output(recorder, reason, code, *, source="initialization", steps=0, tools=0, api_calls=0):
    return {"run_id": recorder.run_id, "mode": recorder.mode, "model": recorder.model,
            "answer": "未完成：" + reason, "citations": [], "gaps": [reason],
            "status": "incomplete" if code == "EXECUTION_LIMIT" else "failed",
            "termination_source": source, "error_code": code,
            "steps_used": steps, "tool_calls": tools, "api_calls": api_calls,
            "verification": {"citation_integrity": "not_accepted", "semantic_support": "not_accepted"}}


class _BudgetExhausted(Exception):
    pass


class Agent:
    def __init__(self, tools, adapter, recorder=None):
        self.tools, self.adapter = tools, adapter
        self.recorder = recorder or Recorder(adapter.mode, adapter.model)

    def run(self, question, history=None, max_steps=8):
        self.steps = self.tool_calls = 0
        self.evidence, self.seen_call_ids, self.pending = {}, set(), []
        history = [] if history is None else history
        self.max_steps = max_steps
        self.recorder.emit("run_started", max_steps=max_steps)
        try:
            validate_input(question, history, max_steps)
            self.adapter.start(question, history)
            while True:
                call = self._request()
                if call is None:
                    continue
                try:
                    name, arguments = self._decode(call)
                    validate_action(name, arguments)
                    self._action_event(call, arguments)
                    if name in ("search_documents", "read_document"):
                        self.tool_calls += 1
                        params = {key: value for key, value in arguments.items() if key != "decision_summary"}
                        try:
                            result = getattr(self.tools, name)(**params)
                        except Exception as exc:
                            result = {"ok": False, "error": {"code": "TOOL_EXECUTION_ERROR",
                                      "message": "工具执行异常：" + type(exc).__name__, "retryable": False}}
                        if name == "read_document" and result.get("ok"):
                            # Providers may hide protocol IDs from the model's
                            # text context. Expose the trusted handle explicitly.
                            result["data"]["read_call_id"] = call["call_id"]
                            self.evidence[call["call_id"]] = copy.deepcopy(result["data"])
                        self.recorder.emit("tool_result", step=self.steps, call_id=call["call_id"],
                                           tool=name, arguments=params, result=result,
                                           result_summary=json.dumps(result, ensure_ascii=False)[:600])
                        self._observe(call, result)
                        continue

                    validate_final(name, arguments, self.evidence)
                    semantic = {"verdict": "not_run", "method": "not_required_for_noncompleted"}
                    if name == "answer":
                        self.recorder.emit("citation_check", step=self.steps, call_id=call["call_id"],
                                           integrity="passed", semantic_support="pending")
                        self._observe(call, {"ok": True, "data": {"candidate_received": True,
                                      "citation_integrity": "passed", "semantic_review": "pending"}})
                        reviewed = self._review(arguments)
                        if reviewed is None:
                            continue
                        semantic = reviewed
                    status = {"answer": "completed", "clarify": "needs_clarification"}.get(name, arguments.get("status"))
                    output = {"run_id": self.recorder.run_id, "mode": self.adapter.mode,
                              "model": self.adapter.model, "answer": arguments["answer"],
                              "citations": arguments["citations"], "gaps": arguments["gaps"],
                              "status": status, "termination_source": "model",
                              "steps_used": self.steps, "tool_calls": self.tool_calls,
                              "api_calls": self.adapter.api_calls,
                              "verification": {"citation_integrity": "passed", "semantic_support": semantic}}
                    return self._finish(output)
                except ValidationError as exc:
                    self._reject(call, exc)
        except _BudgetExhausted:
            output = failure_output(self.recorder, "决策额度已耗尽，尚未得到有效终态或完成证据复核",
                                    "EXECUTION_LIMIT", source="guard", steps=self.steps,
                                    tools=self.tool_calls, api_calls=self.adapter.api_calls)
        except ModelError as exc:
            output = failure_output(self.recorder, str(exc), exc.code, source="adapter", steps=self.steps,
                                    tools=self.tool_calls, api_calls=self.adapter.api_calls)
        except ValidationError as exc:
            output = failure_output(self.recorder, str(exc), exc.code, steps=self.steps)
        return self._finish(output)

    def _request(self, review=None):
        if self.steps >= self.max_steps:
            raise _BudgetExhausted()
        self.steps += 1
        budget = {"max_steps": self.max_steps, "steps_used": self.steps,
                  "remaining_after_this_request": self.max_steps - self.steps}
        self.recorder.emit("model_request", step=self.steps, phase="review" if review else "decision",
                           budget=budget, observation_call_ids=list(self.pending))
        reply = self.adapter.decide(budget, review=review)
        self.recorder.model = self.adapter.model
        calls = reply.get("calls", [])
        if not isinstance(calls, list) or any(not isinstance(call, dict) for call in calls):
            raise ModelError("MODEL_PROTOCOL_ERROR", "模型调用列表格式不合法")
        for call in calls:
            call_id = call.get("call_id")
            if not isinstance(call_id, str) or not call_id or call_id in self.seen_call_ids:
                raise ModelError("MODEL_PROTOCOL_ERROR", "模型调用 ID 缺失或重复，不能安全关联结果")
            self.seen_call_ids.add(call_id)
        if len(calls) != 1:
            self.recorder.emit("model_actions_rejected", step=self.steps,
                               response_id=reply.get("response_id"),
                               calls=[{key: call.get(key) for key in ("call_id", "name", "arguments")}
                                      for call in calls], reason="ONE_ACTION_REQUIRED")
            self.recorder.emit("validation_error", step=self.steps, code="ONE_ACTION_REQUIRED",
                               message="每次响应需且仅需一个动作，未执行本次任何工具")
            result = {"ok": False, "error": {"code": "ONE_ACTION_REQUIRED", "message": "每次只选一个动作"}}
            for call in calls:
                self._observe(call, result)
            if not calls:
                self.adapter.feedback("未收到函数动作；请根据已有观察选择一个允许的函数。")
            return None
        call = calls[0]
        call["response_id"] = reply.get("response_id")
        return call

    def _decode(self, call):
        try:
            arguments = json.loads(call["arguments"])
        except (ValueError, TypeError, KeyError):
            raise ValidationError("INVALID_ARGUMENT", "函数参数必须为合法 JSON 对象") from None
        return call.get("name"), arguments

    def _action_event(self, call, arguments):
        for previous in self.pending:
            self.recorder.emit("transition", observation_call_id=previous, next_step=self.steps,
                               next_action=call.get("name"), next_call_id=call["call_id"],
                               decision_summary=arguments.get("decision_summary", arguments.get("reason")))
        self.pending.clear()
        self.recorder.emit("model_action", step=self.steps, call_id=call["call_id"],
                           response_id=call.get("response_id"), action=call.get("name"), arguments=arguments)

    def _observe(self, call, result):
        self.adapter.observe(call["call_id"], result)
        self.pending.append(call["call_id"])

    def _reject(self, call, exc):
        result = {"ok": False, "error": {"code": exc.code, "message": str(exc), "retryable": True}}
        if exc.code == "CITATION_INVALID":
            result["error"]["available_reads"] = [
                {"read_call_id": call_id, "document_id": source["id"],
                 "version_date": source["version_date"], "start": source["start"], "end": source["end"]}
                for call_id, source in self.evidence.items()]
        self.recorder.emit("validation_error", step=self.steps, call_id=call["call_id"],
                           rejected_action=call.get("name"), **result["error"])
        self._observe(call, result)

    def _review(self, candidate):
        call = self._request(review=candidate)
        if call is None:
            return None
        try:
            name, arguments = self._decode(call)
            validate_action(name, arguments, review=True)
            self._action_event(call, arguments)
            self.recorder.emit("answer_review", step=self.steps, call_id=call["call_id"],
                               verdict=arguments["verdict"], reason=arguments["reason"],
                               method="same_model_review", evaluation_mode=self.adapter.mode)
            if arguments["verdict"] != "supported":
                self._observe(call, {"ok": False, "error": {"code": "ANSWER_UNSUPPORTED",
                              "message": arguments["reason"], "retryable": True}})
                return None
            # The valid assessment itself is the model's terminal acceptance.
            self.adapter.observe(call["call_id"], {"ok": True, "data": {"assessment_recorded": True}})
            return {**arguments, "method": "same_model_review", "mode": self.adapter.mode}
        except ValidationError as exc:
            self._reject(call, exc)
            return None

    def _finish(self, output):
        self.recorder.emit("run_finished", status=output["status"], steps_used=self.steps,
                           tool_calls=self.tool_calls, api_calls=self.adapter.api_calls,
                           termination_source=output["termination_source"],
                           unobserved_call_ids=list(self.pending),
                           pending_state="not_observed_or_no_valid_next_action" if self.pending else "none")
        return self.recorder.clean(output)

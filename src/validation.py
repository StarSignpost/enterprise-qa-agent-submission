"""Deterministic integrity checks, distinct from model semantic review."""

from src.prompts import REVIEW_DEFINITION, TOOL_DEFINITIONS


class ValidationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _schema(value, schema, path="arguments"):
    kind = schema["type"]
    good = {"object": lambda: isinstance(value, dict), "array": lambda: isinstance(value, list),
            "string": lambda: isinstance(value, str), "integer": lambda: type(value) is int}[kind]()
    if not good:
        raise ValidationError("INVALID_ARGUMENT", f"{path} 类型错误")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError("INVALID_ARGUMENT", f"{path} 不在允许值中")
    if kind == "object":
        if set(value) != set(schema["properties"]):
            raise ValidationError("INVALID_ARGUMENT", f"{path} 字段缺失或多余")
        for key, child in schema["properties"].items():
            _schema(value[key], child, path + "." + key)
    elif kind == "array":
        for item in value:
            _schema(item, schema["items"], path + "[]")


def validate_action(name, arguments, *, review=False):
    definitions = [REVIEW_DEFINITION] if review else TOOL_DEFINITIONS
    definition = next((item for item in definitions if item["name"] == name), None)
    if definition is None:
        raise ValidationError("UNKNOWN_ACTION", "动作不在当前阶段白名单中")
    _schema(arguments, definition["parameters"])
    summary = arguments.get("decision_summary", arguments.get("reason", ""))
    if not summary.strip() or len(summary) > 300:
        raise ValidationError("INVALID_ARGUMENT", "需要 1-300 字的公开简要依据")


def validate_final(name, arguments, evidence):
    if not arguments["answer"].strip() or any(not gap.strip() for gap in arguments["gaps"]):
        raise ValidationError("FINAL_OUTPUT_INVALID", "回答/缺口不能是空白字符串")
    if name == "answer" and (not arguments["citations"] or arguments["gaps"]):
        raise ValidationError("FINAL_OUTPUT_INVALID", "完成回答需要原文引用且不能有未解决缺口")
    if name != "answer" and not arguments["gaps"]:
        raise ValidationError("FINAL_OUTPUT_INVALID", "澄清/停止必须说明具体缺口或原因")
    for citation in arguments["citations"]:
        source = evidence.get(citation["read_call_id"])
        if source is None:
            raise ValidationError("CITATION_INVALID", "引用必须来自本轮成功读取")
        start, end = citation["start"], citation["end"]
        if (citation["document_id"] != source["id"]
                or citation["version_date"] != source["version_date"]
                or not source["start"] <= start < end <= source["end"]
                or not citation["quote"]
                or source["text"][start-source["start"]:end-source["start"]] != citation["quote"]):
            raise ValidationError("CITATION_INVALID", "引用 ID、版本、偏移或原文片段不符")


def validate_input(question, history, max_steps):
    if not isinstance(question, str) or not question.strip():
        raise ValidationError("INVALID_INPUT", "question 必须为非空字符串")
    if not isinstance(history, list):
        raise ValidationError("INVALID_INPUT", "history 必须为列表")
    for message in history:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in ("user", "assistant")
                or not isinstance(message["content"], str)):
            raise ValidationError("INVALID_INPUT", "历史只允许 user/assistant 文本消息")
    if len(history) > 20 or len(question) + sum(len(m["content"]) for m in history) > 20000:
        raise ValidationError("INPUT_TOO_LARGE", "历史超过 20 条或总输入超过 20000 字符")
    if type(max_steps) is not int or max_steps < 1:
        raise ValidationError("INVALID_INPUT", "max_steps 必须为正整数")

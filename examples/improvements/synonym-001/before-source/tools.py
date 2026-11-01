"""Local document tools with lexical retrieval and explicit error results.

Tools never select Agent actions. Scenario files only supply documents and
optional persistent faults for a named tool. Search scores are lexical matches,
not document authority, confidence, or version priority.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path


class DatasetError(ValueError):
    """An invalid/unreadable dataset must not become an empty search index."""


# A small, explicit vocabulary; this is not general semantic retrieval.
_ALIASES = {
    "费用报销": "报销",
    "报账": "报销",
    "报帐": "报销",
    "截止时间": "期限",
    "时限": "期限",
    "最迟": "期限",
    "多少天": "期限",
    "几天": "期限",
    "所需资料": "材料",
    "凭证": "材料",
    "单据": "材料",
}
_STOP_WORDS = (
    "多长时间", "请问", "多久", "需要", "什么", "是否", "可以",
    "公司", "得在", "办理", "一下", "的是", "那", "吗", "呢", "内办",
)


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    for source, target in _ALIASES.items():
        normalized = normalized.replace(source, target)
    for stop_word in _STOP_WORDS:
        normalized = normalized.replace(stop_word, " ")
    terms = set()
    for word in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized):
        if "\u4e00" <= word[0] <= "\u9fff":
            terms.update(word[index:index + 2] for index in range(len(word) - 1))
        else:
            terms.add(word)
    return terms


def _error(code: str, message: str, *, retryable: bool = False) -> dict:
    # A failure has no data/matches field, so it cannot look like zero matches.
    return {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable},
    }


class KnowledgeTools:
    """Two tools over an isolated, validated document snapshot.

    search_documents(query, limit=5): candidate metadata and short summaries.
    read_document(document_id, start=0, length=500): verbatim character slice.
    Returned offsets use Python Unicode code points, with end exclusive.
    """

    TOOL_NAMES = frozenset({"search_documents", "read_document"})

    def __init__(self, documents: list[dict], faults: dict | None = None):
        if not isinstance(documents, list):
            raise DatasetError("documents 必须是列表")
        if faults is None:
            faults = {}
        if not isinstance(faults, dict) or any(
            key not in self.TOOL_NAMES or type(value) is not bool
            for key, value in faults.items()
        ):
            raise DatasetError("faults 只允许工具名到布尔值的映射")

        self._documents = {}
        self._index = {}
        self._faults = frozenset(key for key, enabled in faults.items() if enabled)
        required = {"id", "title", "version_date", "content"}
        for document in documents:
            if (not isinstance(document, dict) or not required <= set(document)
                    or set(document) - required - {"scope"}):
                raise DatasetError("文档需含 id/title/version_date/content，仅允许可选 scope")
            if any(not isinstance(value, str) or not value.strip()
                   for value in document.values()):
                raise DatasetError("文档字段必须为非空字符串")
            if "scope" in document and document["scope"] not in document["content"]:
                raise DatasetError("scope 必须是正文中确实存在的范围说明")
            try:
                parsed_date = date.fromisoformat(document["version_date"])
            except ValueError as exc:
                raise DatasetError("version_date 必须为有效的 YYYY-MM-DD 日期") from exc
            if parsed_date.isoformat() != document["version_date"]:
                raise DatasetError("version_date 必须为 YYYY-MM-DD 日期")
            document_id = document["id"]
            if document_id in self._documents:
                raise DatasetError("同一资料快照不能包含重复文档 ID")
            # Copy fields so later caller mutations cannot change this snapshot.
            self._documents[document_id] = dict(document)
            self._index[document_id] = (
                _terms(document["title"]), _terms(document["content"])
            )

    @classmethod
    def from_file(cls, path: str | Path) -> KnowledgeTools:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DatasetError(f"无法读取资料文件（{type(exc).__name__}）") from exc
        if not isinstance(payload, dict) or "documents" not in payload:
            raise DatasetError("资料文件必须包含 documents")
        if set(payload) - {"documents", "faults"}:
            raise DatasetError("资料文件只允许 documents 和 faults，不接受动作或答案配置")
        if "faults" in payload and not isinstance(payload["faults"], dict):
            raise DatasetError("faults 必须为工具名到布尔值的映射")
        return cls(payload["documents"], payload.get("faults", {}))

    def search_documents(self, query: str, limit: int = 5) -> dict:
        if not isinstance(query, str) or not query.strip():
            return _error("INVALID_ARGUMENT", "query 必须为非空字符串")
        if type(limit) is not int or not 1 <= limit <= 20:
            return _error("INVALID_ARGUMENT", "limit 必须是 1 到 20 的整数")
        if "search_documents" in self._faults:
            return _error("TOOL_UNAVAILABLE", "已注入故障：检索工具不可用")

        query_terms = _terms(query)
        matches = []
        for document_id, document in self._documents.items():
            title_terms, body_terms = self._index[document_id]
            overlap = query_terms & (title_terms | body_terms)
            if not overlap:
                continue
            # Title matches have a small extra weight. Dates do not affect rank.
            score = len(overlap) + len(query_terms & title_terms)
            matches.append({
                "id": document_id,
                "version_date": document["version_date"],
                "title": document["title"],
                "summary": document["content"][:100],
                "score": score,
                **({"scope": document["scope"]} if "scope" in document else {}),
            })
        matches.sort(key=lambda match: (-match["score"], match["id"]))
        return {"ok": True, "data": {
            "query": query,
            "matches": matches[:limit],
            "total_matches": len(matches),
            "has_more": len(matches) > limit,
        }}

    def read_document(
        self, document_id: str, start: int = 0, length: int = 500
    ) -> dict:
        if not isinstance(document_id, str) or not document_id.strip():
            return _error("INVALID_ARGUMENT", "document_id 必须为非空字符串")
        if type(start) is not int or start < 0:
            return _error("INVALID_ARGUMENT", "start 必须为非负整数")
        if type(length) is not int or not 1 <= length <= 2000:
            return _error("INVALID_ARGUMENT", "length 必须是 1 到 2000 的整数")
        if "read_document" in self._faults:
            return _error("TOOL_UNAVAILABLE", "已注入故障：原文读取工具不可用")
        document = self._documents.get(document_id)
        if document is None:
            return _error("DOCUMENT_NOT_FOUND", "未找到指定文档 ID")
        content = document["content"]
        if start >= len(content):
            return _error("INVALID_ARGUMENT", "start 超出正文范围")
        end = min(start + length, len(content))
        return {"ok": True, "data": {
            "id": document["id"],
            "version_date": document["version_date"],
            "title": document["title"],
            "text": content[start:end],
            "start": start,
            "end": end,
            "total_length": len(content),
            "has_more": end < len(content),
            **({"scope": document["scope"]} if "scope" in document else {}),
        }}

    def snapshot(self) -> dict:
        """Return an independent copy for evidence, never for choosing actions."""
        return {"documents": [dict(doc) for doc in self._documents.values()],
                "faults": {name: True for name in sorted(self._faults)}}

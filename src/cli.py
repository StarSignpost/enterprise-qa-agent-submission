"""Run one turn; explicit modes, immutable evidence directories, no downgrade."""

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import sys

from src.agent import Agent, Recorder, failure_output, now
from src.mock_model import MockAdapter
from src.models import DeepSeekResponsesAdapter, ModelError
from src.tools import DatasetError, KnowledgeTools
from src.validation import ValidationError, validate_input


def _write(path, value, recorder):
    path.write_text(json.dumps(recorder.clean(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="企业知识问答：真实模型或独立离线 Mock")
    parser.add_argument("--mode", choices=("real", "mock"), required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--max-steps", type=int, default=8, help="所有决策与语义复核请求共用额度")
    parser.add_argument("--mock-script")
    parser.add_argument("--output-dir", required=True, help="必须是尚不存在的本次运行目录")
    args = parser.parse_args(argv)
    directory = Path(args.output_dir)
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except OSError:
        print(json.dumps({"mode": args.mode, "status": "failed", "error_code": "OUTPUT_DIRECTORY_ERROR",
                          "answer": "输出目录已存在或不可写，未覆盖任何证据"}, ensure_ascii=True))
        return 1
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    model = os.environ.get("DEEPSEEK_MODEL") if args.mode == "real" else "mock-script-v1"
    recorder = Recorder(args.mode, model, directory / "trace.jsonl", secrets=(key,))
    started = now()
    adapter = None
    data_digest = mock_digest = None
    try:
        try:
            input_data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise ValidationError("INVALID_INPUT", "无法读取合法的 UTF-8 JSON 输入") from None
        if not isinstance(input_data, dict) or not {"question"} <= set(input_data) <= {"question", "history"}:
            raise ValidationError("INVALID_INPUT", "输入只允许 question 与可选 history")
        validate_input(input_data["question"], input_data.get("history", []), args.max_steps)
        tools = KnowledgeTools.from_file(args.data)
        data_digest = hashlib.sha256(Path(args.data).read_bytes()).hexdigest()
        _write(directory / "input.json", input_data, recorder)
        _write(directory / "documents.json", tools.snapshot(), recorder)
        if args.mode == "real":
            if args.mock_script:
                raise ValidationError("MODE_MISMATCH", "真实模式不接受 Mock 脚本")
            adapter = DeepSeekResponsesAdapter(key, model)
        else:
            if not args.mock_script:
                raise ValidationError("MOCK_SCRIPT_REQUIRED", "离线模式必须显式指定动作脚本")
            adapter = MockAdapter.from_file(args.mock_script)
            mock_digest = hashlib.sha256(Path(args.mock_script).read_bytes()).hexdigest()
        output = Agent(tools, adapter, recorder).run(
            input_data["question"], input_data.get("history", []), args.max_steps)
    except (ValidationError, DatasetError, ModelError) as exc:
        output = failure_output(recorder, str(exc), getattr(exc, "code", "DATASET_ERROR"))
        recorder.emit("run_started", max_steps=args.max_steps, initialization_failed=True)
        recorder.emit("run_finished", status="failed", termination_source="initialization",
                      error_code=output["error_code"], steps_used=0, tool_calls=0, api_calls=0)
    except OSError:
        print(json.dumps({"mode": args.mode, "status": "failed", "error_code": "EVIDENCE_WRITE_ERROR",
                          "answer": "证据保存失败，未声称保存成功"}, ensure_ascii=True))
        return 1

    try:
        _write(directory / "output.json", output, recorder)
        root = Path(__file__).resolve().parents[1]
        source_paths = sorted((root / "src").glob("*.py"))
        run = {"run_id": recorder.run_id, "mode": args.mode, "model": output["model"],
               "started_at": started, "finished_at": now(), "command": ["python", "-m", "src.cli", *(argv if argv is not None else sys.argv[1:])],
               "python_version": platform.python_version(),
               "max_steps": args.max_steps, "steps_used": output["steps_used"],
               "tool_calls": output["tool_calls"], "api_calls": output["api_calls"],
               "status": output["status"], "termination_source": output["termination_source"],
               "provider": "deepseek" if args.mode == "real" else "mock",
               "endpoint": DeepSeekResponsesAdapter.ENDPOINT if args.mode == "real" else None,
               "reasoning_effort": "none" if args.mode == "real" else None,
               "data_sha256": data_digest,
               "source_sha256": {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
               "mock_script_sha256": mock_digest}
        _write(directory / "run.json", run, recorder)
    except OSError:
        print(json.dumps({"mode": args.mode, "status": "failed", "error_code": "EVIDENCE_WRITE_ERROR",
                          "answer": "证据保存失败，未声称保存成功"}, ensure_ascii=True))
        return 1
    # ASCII JSON escapes make the CLI portable across Windows console encodings.
    print(json.dumps(output, ensure_ascii=True))
    return {"completed": 0, "needs_clarification": 0, "incomplete": 2, "failed": 1}[output["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

"""Prompt for an ephemeral key without putting it in argv, files or reports."""

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

from tests.run_validation import main as validate


def main():
    parser = argparse.ArgumentParser(description="DeepSeek validation; credential stays in process memory")
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--test", action="append")
    args = parser.parse_args()
    key = getpass.getpass("DeepSeek API key (hidden): ")
    previous = {name: os.environ.get(name) for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL")}
    try:
        os.environ["DEEPSEEK_API_KEY"] = key
        os.environ["DEEPSEEK_MODEL"] = args.model
        arguments = ["--live", "--output-dir", args.output_dir]
        for test_name in args.test or ["tests.test_live.LiveAcceptanceTests"]:
            arguments += ["--test", test_name]
        code = validate(arguments)
        invocation = {"entry_command": ["python", "-m", "tests.run_private_live", *sys.argv[1:]],
                      "credential_channel": "hidden getpass input; process environment only",
                      "provider": "deepseek", "model": args.model,
                      "key_saved": False, "delegated_module": "tests.run_validation"}
        (Path(args.output_dir) / "invocation.json").write_text(
            json.dumps(invocation, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return code
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        key = None


if __name__ == "__main__":
    raise SystemExit(main())

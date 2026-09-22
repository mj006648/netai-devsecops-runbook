"""Check AI lessons using the standard library; optionally run trusted Python blocks.

Python blocks run in separate temporary directories. Shell blocks are only
syntax-checked. This is a document/example check, not a GPU benchmark.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from urllib.parse import unquote

BOOK = Path(__file__).resolve().parents[1]
ROOT = BOOK.parents[2]


def check(run_python=False):
    paths = sorted(BOOK.rglob("*.md")) + [ROOT / "ai/README.md"]
    errors = []
    snippets = []
    links = tables = bash_blocks = 0
    for path in paths:
        source = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT))
        fence = None
        body = []
        width = None
        language = ""
        start = 0
        for number, line in enumerate(source.splitlines(), 1):
            marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
            if fence is not None:
                if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                    code = "\n".join(body)
                    label = f"{relative}:{start}"
                    if language == "python":
                        try:
                            ast.parse(code, filename=label)
                            snippets.append((label, code))
                        except SyntaxError as error:
                            errors.append(f"{label}: {error}")
                    elif language in ("bash", "sh"):
                        bash_blocks += 1
                        result = subprocess.run(
                            ["bash", "-n"], input=code, capture_output=True,
                            text=True, timeout=10,
                        )
                        if result.returncode:
                            errors.append(f"{label}: {result.stderr.strip()}")
                    fence = None
                    width = None
                else:
                    body.append(line)
                continue
            if marker:
                fence, language, start = marker[1], marker[2].strip(), number
                body = []
                continue
            if line != line.rstrip():
                errors.append(f"{relative}:{number}: trailing whitespace")
            if line.startswith("|") and line.endswith("|"):
                cells = len(re.split(r"(?<!\\)\|", line)) - 2
                if width is None:
                    tables += 1
                    width = cells
                elif width != cells:
                    errors.append(f"{relative}:{number}: table width {cells}, expected {width}")
            else:
                width = None
            for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", line):
                target = target.split(' "', 1)[0].strip("<>")
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                links += 1
                target = unquote(target.split("#", 1)[0])
                if target and not (path.parent / target).resolve().exists():
                    errors.append(f"{relative}:{number}: missing link {target}")
        if fence is not None:
            errors.append(f"{relative}:{start}: unclosed fence")
        if source.count("<details>") != source.count("</details>"):
            errors.append(f"{relative}: unbalanced details tags")

    passed = 0
    if run_python and not errors:
        for label, code in snippets:
            with tempfile.TemporaryDirectory(prefix="ai-lesson-check-") as scratch:
                process = subprocess.Popen(
                    [sys.executable, "-B", "-c", code], cwd=scratch,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True,
                )
                try:
                    output, stderr = process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    errors.append(f"{label}: timeout")
                    continue
                if process.returncode or stderr:
                    errors.append(f"{label}: exit {process.returncode}: {stderr.strip()}")
                else:
                    passed += 1
    return {
        "python_version": sys.version.split()[0],
        "markdown_files": len(paths), "relative_links": links, "tables": tables,
        "bash_syntax_blocks": bash_blocks, "python_syntax_blocks": len(snippets),
        "python_executed": passed, "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-python", action="store_true",
        help="execute the trusted, standalone Python blocks in the AI textbook",
    )
    arguments = parser.parse_args()
    result = check(arguments.run_python)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())

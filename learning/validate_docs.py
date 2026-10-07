"""Check the five textbooks and their diagrams without extra dependencies.

Reuses the existing AI lesson checker for tables, fences and code syntax.
Python snippets run only with --run-python, in temporary working directories.
Shell snippets are syntax-checked and never executed.
"""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BOOKS = [
    ROOT / "hardware/learning/server-hardware",
    ROOT / "linux/learning/linux-kernel",
    ROOT / "kubernetes/networking/networking-foundations",
    ROOT / "kubernetes/storage/data-systems-foundations",
    ROOT / "ai/learning/ai-infrastructure",
    ROOT / "learning",
]


def prose_lines(source):
    """Skip fenced examples when looking for headings and links."""
    fence = None
    for number, line in enumerate(source.splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
        else:
            yield number, line


def heading_ids(source):
    ids = set()
    counts = {}
    for _, line in prose_lines(source):
        heading = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if heading:
            label = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading[1])
            label = re.sub(r"<[^>]+>", "", label).lower()
            slug = re.sub(r"[^\w\- ]", "", label).replace(" ", "-")
            suffix = counts.get(slug, 0)
            counts[slug] = suffix + 1
            ids.add(slug + (f"-{suffix}" if suffix else ""))
        ids.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', line))
    return ids


def check_heredocs(paths, run_python):
    """Also check Python examples embedded in shell heredocs."""
    snippets = []
    errors = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?m)^\s*python3[^\n]*<<\s*['\"]?(\w+)['\"]?\s*\n", source):
            tail = source[match.end():]
            end = re.search(r"(?m)^" + re.escape(match[1]) + r"\s*$", tail)
            if end is None:
                continue
            code = tail[:end.start()]
            label = f"{path.relative_to(ROOT)}:{source[:match.start()].count(chr(10)) + 1}"
            try:
                ast.parse(code, filename=label)
                snippets.append((label, code))
            except SyntaxError as error:
                errors.append(f"{label}: Python heredoc syntax: {error}")
    executed = 0
    if run_python and not errors:
        for label, code in snippets:
            with tempfile.TemporaryDirectory(prefix="textbook-heredoc-") as scratch:
                process = subprocess.Popen(
                    [sys.executable, "-B", "-c", code], cwd=scratch,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True,
                )
                try:
                    _, stderr = process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    errors.append(f"{label}: Python heredoc timeout")
                    continue
                if process.returncode or stderr:
                    errors.append(f"{label}: exit {process.returncode}: {stderr.strip()}")
                else:
                    executed += 1
    return {"python_syntax_blocks": len(snippets), "python_executed": executed, "errors": errors}


def check(run_python=False):
    spec = importlib.util.spec_from_file_location(
        "existing_lesson_checker", ROOT / "ai/learning/ai-infrastructure/examples/check_lessons.py"
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    errors = []
    syntax_reports = {}
    for book in BOOKS:
        checker.BOOK = book
        report = checker.check(run_python=run_python)
        syntax_reports[str(book.relative_to(ROOT))] = report
        errors.extend(report["errors"])

    paths = sorted({p for book in BOOKS for p in book.rglob("*.md")})
    heredoc_report = check_heredocs(paths, run_python)
    errors.extend(heredoc_report["errors"])
    heading_cache = {}
    local_links = anchors = images = mermaid = 0
    svg_paths = set()
    chapter_count = 0
    for path in paths:
        source = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT))
        mermaid += len(re.findall(r"^```mermaid\s*$", source, flags=re.M))
        if path.parent in BOOKS[:-1] and re.match(r"^\d\d[a-z]?-", path.name):
            chapter_count += 1
            if "```mermaid" not in source:
                errors.append(f"{relative}: chapter has no Mermaid diagram")
        for number, line in prose_lines(source):
            targets = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", line)
            targets += re.findall(r'(?:src|href)=["\']([^"\']+)["\']', line)
            for raw in targets:
                target = raw.split(' "', 1)[0].strip("<>")
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("//"):
                    continue
                target_path, _, fragment = target.partition("#")
                linked = (path.parent / unquote(target_path)).resolve() if target_path else path
                local_links += 1
                if not linked.exists():
                    errors.append(f"{relative}:{number}: missing target {target}")
                    continue
                if fragment and linked.suffix == ".md":
                    anchors += 1
                    if linked not in heading_cache:
                        heading_cache[linked] = heading_ids(linked.read_text(encoding="utf-8"))
                    if unquote(fragment) not in heading_cache[linked]:
                        errors.append(f"{relative}:{number}: missing heading {target}")
                if linked.suffix.lower() in (".svg", ".jpg", ".jpeg", ".png", ".webp"):
                    images += 1
                    if linked.suffix == ".svg":
                        svg_paths.add(linked)
            for alt in re.findall(r"!\[([^\]]*)\]\(", line):
                if not alt.strip():
                    errors.append(f"{relative}:{number}: image has no alternative text")

    all_svgs = sorted({p for book in BOOKS for p in book.rglob("*.svg")})
    for path in all_svgs:
        relative = str(path.relative_to(ROOT))
        try:
            node = ET.parse(path).getroot()
            ns = "{http://www.w3.org/2000/svg}"
            if node.find(ns + "title") is None or node.find(ns + "desc") is None:
                errors.append(f"{relative}: SVG lacks title or description")
            if path not in svg_paths:
                errors.append(f"{relative}: SVG is not linked from a textbook")
        except ET.ParseError as error:
            errors.append(f"{relative}: invalid SVG: {error}")

    photos = sorted((BOOKS[0] / "assets/photos").glob("*.jpg"))
    credits_path = BOOKS[0] / "assets/photos/README.md"
    credits = credits_path.read_text(encoding="utf-8") if credits_path.exists() else ""
    for photo in photos:
        if photo.read_bytes()[:3] != b"\xff\xd8\xff":
            errors.append(f"{photo.name}: download is not a JPEG")
        if photo.name not in credits:
            errors.append(f"{photo.name}: photo has no source/license entry")

    return {
        "python_version": sys.version.split()[0],
        "markdown_files": len(paths),
        "numbered_chapters": chapter_count,
        "local_links": local_links,
        "heading_links": anchors,
        "image_links": images,
        "mermaid_blocks": mermaid,
        "svg_files": len(all_svgs),
        "licensed_photo_files": len(photos),
        "book_syntax_and_examples": syntax_reports,
        "python_in_shell_heredocs": heredoc_report,
        "errors": sorted(set(errors)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-python", action="store_true", help="execute trusted textbook Python snippets")
    parser.add_argument("--output", type=Path, help="also save the JSON report")
    args = parser.parse_args()
    report = check(args.run_python)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())

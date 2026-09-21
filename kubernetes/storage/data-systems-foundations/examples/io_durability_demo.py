"""Educational file IO ordering demo: write, flush, fsync, replace, directory fsync.

This program is intentionally small and stdlib-only. It illustrates ordering and
reports timings/checksums for one temporary file. It is not a power-loss test, a
filesystem certification, a device benchmark, or thesis evidence.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter_ns
from typing import Callable, BinaryIO

MIN_SIZE_MIB = 1
MAX_SIZE_MIB = 16
DEFAULT_SIZE_MIB = 1
CHUNK_SIZE = 1024 * 1024
OUTPUT_NAME = "durability-demo.bin"

UNSUPPORTED_DIR_FSYNC_ERRNOS = {
    errno.EINVAL,
    getattr(errno, "ENOTSUP", 95),
    getattr(errno, "EOPNOTSUPP", 95),
}
WINDOWS_DIRECTORY_OPEN_UNSUPPORTED_ERRNOS = {errno.EACCES, errno.EINVAL}


def bounded_size_mib(value: str) -> int:
    """argparse type for the deliberately tiny demo size bound."""
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer MiB value") from exc
    if not MIN_SIZE_MIB <= parsed <= MAX_SIZE_MIB:
        raise argparse.ArgumentTypeError(f"must be between {MIN_SIZE_MIB} and {MAX_SIZE_MIB} MiB")
    return parsed


def existing_directory(value: str) -> Path:
    """argparse type requiring an existing scratch parent directory."""
    path = Path(value).expanduser()
    if not path.is_dir():
        raise argparse.ArgumentTypeError("must be an existing directory")
    return path


def make_payload(size_mib: int) -> bytes:
    """Create deterministic demo bytes without reading host or environment data."""
    if not MIN_SIZE_MIB <= size_mib <= MAX_SIZE_MIB:
        raise ValueError(f"size_mib must be between {MIN_SIZE_MIB} and {MAX_SIZE_MIB}")
    pattern = b"netai educational buffered-io durability ordering demo\n"
    length = size_mib * CHUNK_SIZE
    return (pattern * ((length // len(pattern)) + 1))[:length]


def _write_all(stream: BinaryIO, data: bytes) -> None:
    """Write every byte or raise; handles streams that report short writes."""
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = stream.write(view[offset : offset + CHUNK_SIZE])
        if written is None:
            raise OSError("write returned None; no byte progress was confirmed")
        if not isinstance(written, int):
            raise OSError(f"write returned invalid byte count {written!r}")
        if written <= 0:
            raise OSError("short write made no progress")
        if written > len(view) - offset:
            raise OSError("write returned more bytes than requested")
        offset += written


def _default_file_fsync(stream: BinaryIO) -> None:
    os.fsync(stream.fileno())


def _default_directory_fsync(directory: Path) -> dict:
    """Best-effort directory fsync; unsupported platforms report unknown."""
    flags = getattr(os, "O_RDONLY", 0)
    fd = None
    try:
        fd = os.open(directory, flags)
        os.fsync(fd)
    except OSError as exc:
        known_unsupported = exc.errno in UNSUPPORTED_DIR_FSYNC_ERRNOS
        known_windows_directory_open_failure = os.name == "nt" and exc.errno in WINDOWS_DIRECTORY_OPEN_UNSUPPORTED_ERRNOS
        if known_unsupported or known_windows_directory_open_failure:
            return {
                "status": "unknown_not_tested",
                "guaranteed_atomic_persistence": False,
                "detail": "directory fsync was unsupported or unavailable on this platform/filesystem",
            }
        raise
    finally:
        if fd is not None:
            os.close(fd)
    return {
        "status": "succeeded",
        "guaranteed_atomic_persistence": False,
        "detail": "directory fsync call returned successfully, but this demo still cannot prove crash persistence",
    }


def _timed(phases: dict, name: str, action: Callable[[], object]) -> object:
    start = perf_counter_ns()
    try:
        return action()
    finally:
        phases[name] = {"elapsed_ns": perf_counter_ns() - start}


def write_replace_verify(
    scratch_dir: Path,
    payload: bytes,
    *,
    flush_file: Callable[[BinaryIO], None] | None = None,
    fsync_file: Callable[[BinaryIO], None] | None = None,
    replace_file: Callable[[Path, Path], None] | None = None,
    fsync_directory: Callable[[Path], dict] | None = None,
) -> dict:
    """Write payload to a temp file, fsync it, replace final file, fsync directory."""
    scratch_dir = Path(scratch_dir)
    temp_path = scratch_dir / f".{OUTPUT_NAME}.tmp"
    final_path = scratch_dir / OUTPUT_NAME
    phases: dict[str, dict] = {}
    flush_file = flush_file or (lambda stream: stream.flush())
    fsync_file = fsync_file or _default_file_fsync
    replace_file = replace_file or os.replace
    fsync_directory = fsync_directory or _default_directory_fsync

    expected_sha256 = hashlib.sha256(payload).hexdigest()

    with temp_path.open("wb") as stream:
        _timed(phases, "buffered_write", lambda: _write_all(stream, payload))
        _timed(phases, "flush_python_buffer", lambda: flush_file(stream))
        _timed(phases, "file_fsync", lambda: fsync_file(stream))

    _timed(phases, "same_directory_os_replace", lambda: replace_file(temp_path, final_path))
    directory_fsync = _timed(phases, "directory_fsync", lambda: fsync_directory(scratch_dir))

    def verify() -> dict:
        data = final_path.read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        return {
            "actual_bytes": len(data),
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "hash_match": actual_sha256 == expected_sha256,
        }

    verification = _timed(phases, "readback_checksum", verify)
    if not verification["hash_match"] or verification["actual_bytes"] != len(payload):
        raise RuntimeError("readback checksum or byte count mismatch")

    return {"phases": phases, "verification": verification, "directory_fsync": directory_fsync}


def run_demo(size_mib: int = DEFAULT_SIZE_MIB, scratch_parent: Path | None = None) -> dict:
    """Run the demo in a private TemporaryDirectory child and return JSON-safe data."""
    if not MIN_SIZE_MIB <= size_mib <= MAX_SIZE_MIB:
        raise ValueError(f"size_mib must be between {MIN_SIZE_MIB} and {MAX_SIZE_MIB}")
    if scratch_parent is not None and not Path(scratch_parent).is_dir():
        raise ValueError("scratch_parent must be an existing directory")

    payload = make_payload(size_mib)
    cleaned = False
    with tempfile.TemporaryDirectory(prefix="io-durability-demo-", dir=scratch_parent) as scratch_name:
        scratch_dir = Path(scratch_name)
        result = write_replace_verify(scratch_dir, payload)
        cleaned = True

    return {
        "educational_only": True,
        "actual_bytes": result["verification"]["actual_bytes"],
        "hash_match": result["verification"]["hash_match"],
        "sha256": result["verification"]["actual_sha256"],
        "phases": result["phases"],
        "directory_fsync": result["directory_fsync"],
        "temporary_child_removed": cleaned,
        "visibility_durability_distinction": (
            "visibility: os.replace in one directory makes the new name visible atomically on supported platforms; "
            "file fsync and directory fsync address different persistence steps, and this demo does not prove "
            "survival across process, OS, controller, or power failure."
        ),
        "filesystem_caveat": (
            "Results depend on the OS, filesystem, mount options, storage controller, cache policy, and hardware. "
            "No crash was injected, no cold-cache state is guaranteed, and timings are educational observations only."
        ),
        "supported_platform_caveat": (
            "The ordering uses Python buffered file flush, os.fsync, and same-directory os.replace. "
            "Directory fsync is reported as unknown/not tested when unsupported."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size-mib",
        type=bounded_size_mib,
        default=DEFAULT_SIZE_MIB,
        help=f"demo payload size in MiB ({MIN_SIZE_MIB}..{MAX_SIZE_MIB}; default: {DEFAULT_SIZE_MIB})",
    )
    parser.add_argument(
        "--scratch-parent",
        type=existing_directory,
        default=None,
        help="optional existing directory under which a private TemporaryDirectory child is created",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_demo(size_mib=args.size_mib, scratch_parent=args.scratch_parent)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"io durability demo failed: {type(exc).__name__}: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

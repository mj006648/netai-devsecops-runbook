from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import io_durability_demo as demo

ROOT = Path(__file__).parent


class IODurabilityDemoTests(unittest.TestCase):
    def test_mocked_order_flush_before_file_fsync_before_rename_before_directory_fsync(self):
        parent = mock.Mock()
        real_replace = os.replace
        with tempfile.TemporaryDirectory() as scratch_name:
            scratch_dir = Path(scratch_name)
            payload = demo.make_payload(1)[:8192]

            def flush_file(stream):
                stream.flush()

            def fsync_file(stream):
                self.assertGreater(stream.fileno(), -1)

            def replace_file(source, target):
                real_replace(source, target)

            def fsync_directory(directory):
                self.assertEqual(directory, scratch_dir)
                return {"status": "mocked", "guaranteed_atomic_persistence": False, "detail": "unit test"}

            parent.attach_mock(mock.Mock(side_effect=flush_file), "flush")
            parent.attach_mock(mock.Mock(side_effect=fsync_file), "file_fsync")
            parent.attach_mock(mock.Mock(side_effect=replace_file), "replace")
            parent.attach_mock(mock.Mock(side_effect=fsync_directory), "directory_fsync")

            result = demo.write_replace_verify(
                scratch_dir,
                payload,
                flush_file=parent.flush,
                fsync_file=parent.file_fsync,
                replace_file=parent.replace,
                fsync_directory=parent.directory_fsync,
            )

        self.assertTrue(result["verification"]["hash_match"])
        self.assertEqual(
            [call[0] for call in parent.mock_calls],
            ["flush", "file_fsync", "replace", "directory_fsync"],
        )

    def test_invalid_size_bounds_are_rejected(self):
        for value in (0, 17):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "between"):
                    demo.run_demo(size_mib=value)
        for value in ("0", "17", "not-an-int"):
            with self.subTest(argv=value):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "io_durability_demo.py"), "--size-mib", value],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("--size-mib", result.stderr)

    def test_real_scratch_demo_hashes_cleans_up_and_preserves_preexisting_sentinel(self):
        with tempfile.TemporaryDirectory() as parent_name:
            parent = Path(parent_name)
            sentinel = parent / "sentinel.txt"
            sentinel.write_text("do not touch\n", encoding="utf-8")
            before = {path.name for path in parent.iterdir()}

            result = demo.run_demo(size_mib=1, scratch_parent=parent)

            after = {path.name for path in parent.iterdir()}
            self.assertEqual(before, after)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do not touch\n")
            self.assertTrue(result["educational_only"])
            self.assertEqual(result["actual_bytes"], 1024 * 1024)
            self.assertTrue(result["hash_match"])
            self.assertTrue(result["temporary_child_removed"])
            self.assertIn("visibility", result["visibility_durability_distinction"])
            self.assertIn("No crash", result["filesystem_caveat"])

    def test_write_all_rejects_none_return_as_unconfirmed_progress(self):
        stream = mock.Mock()
        stream.write.return_value = None
        with self.assertRaisesRegex(OSError, "None"):
            demo._write_all(stream, b"abc")

    def test_write_all_rejects_invalid_return_values(self):
        for returned in ("3", 4):
            with self.subTest(returned=returned):
                stream = mock.Mock()
                stream.write.return_value = returned
                with self.assertRaisesRegex(OSError, "invalid|more bytes"):
                    demo._write_all(stream, b"abc")

    def test_write_all_accepts_normal_partial_writes(self):
        chunks = []

        class PartialWriter:
            def write(self, data):
                chunk = bytes(data[:2])
                chunks.append(chunk)
                return len(chunk)

        demo._write_all(PartialWriter(), b"abcde")
        self.assertEqual(chunks, [b"ab", b"cd", b"e"])

    def test_short_write_without_progress_raises(self):
        stream = mock.Mock()
        stream.write.return_value = 0
        with self.assertRaisesRegex(OSError, "short write"):
            demo._write_all(stream, b"abc")

    def test_errors_propagate_and_are_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as scratch_name:
            scratch_dir = Path(scratch_name)
            with self.assertRaisesRegex(OSError, "fsync failed"):
                demo.write_replace_verify(
                    scratch_dir,
                    b"payload",
                    fsync_file=mock.Mock(side_effect=OSError("fsync failed")),
                )


    def test_directory_fsync_known_unsupported_is_reported_unknown(self):
        with mock.patch("io_durability_demo.os.open", side_effect=OSError(demo.errno.EINVAL, "unsupported")):
            result = demo._default_directory_fsync(Path("/tmp"))
        self.assertEqual(result["status"], "unknown_not_tested")
        self.assertFalse(result["guaranteed_atomic_persistence"])

    def test_directory_fsync_does_not_swallow_real_or_unexpected_errors(self):
        for err in (demo.errno.EIO, demo.errno.EBADF, demo.errno.ENOTDIR):
            with self.subTest(errno=err):
                with mock.patch("io_durability_demo.os.open", side_effect=OSError(err, "real failure")):
                    with self.assertRaises(OSError) as caught:
                        demo._default_directory_fsync(Path("/tmp"))
                self.assertEqual(caught.exception.errno, err)

    def test_windows_directory_fsync_does_not_swallow_all_oserrors(self):
        with mock.patch("io_durability_demo.os.name", "nt"):
            with mock.patch("io_durability_demo.os.open", side_effect=OSError(demo.errno.EIO, "real failure")):
                with self.assertRaises(OSError) as caught:
                    demo._default_directory_fsync(Path("C:/scratch"))
        self.assertEqual(caught.exception.errno, demo.errno.EIO)

    def test_cli_outputs_json_without_host_identifiers(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "io_durability_demo.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["educational_only"])
        self.assertTrue(data["hash_match"])
        self.assertEqual(data["actual_bytes"], 1024 * 1024)
        forbidden_keys = {"hostname", "username", "user", "home", "scratch_path"}
        self.assertTrue(forbidden_keys.isdisjoint(data))


if __name__ == "__main__":
    unittest.main()

import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest

from replay_demo import load_events, simulate

ROOT = Path(__file__).parent


class ReplayDemoTests(unittest.TestCase):
    def setUp(self):
        self.rows = load_events(ROOT / "events.jsonl")

    def test_outage_replay_keeps_logical_sets_and_physical_duplicates_distinct(self):
        result = simulate(self.rows)
        self.assertTrue(result["simulation"])
        self.assertEqual(result["source_records"], 10)
        self.assertEqual(result["logical_events"], 8)
        self.assertEqual(result["duplicate_source_records"], 2)
        self.assertEqual(result["hot_documents"], 8)
        self.assertEqual(result["archive_records"], 10)
        self.assertTrue(result["logical_sink_sets_match"])
        self.assertGreater(result["hot_visible_during_archive_pause"], 0)
        self.assertTrue(result["hot_retry_was_simulated"])

    def test_arrival_order_does_not_establish_business_state(self):
        result = simulate(self.rows)
        self.assertEqual(result["naive_arrival_state"]["run-002"], "Preparing")
        self.assertEqual(result["source_sequence_state"]["run-002"], "Ready")

    def test_retention_gap_does_not_silently_skip_ahead(self):
        result = simulate(self.rows, "retention-gap")
        self.assertEqual(result["missing_source_offsets"], [0, 1, 2])
        self.assertEqual(result["archive_next_offset"], 0)
        self.assertFalse(result["logical_sink_sets_match"])

    def test_conflicting_identity_is_rejected(self):
        rows = deepcopy(self.rows)
        rows[-1]["state"] = "Failed"
        with self.assertRaisesRegex(ValueError, "conflicting"):
            simulate(rows)

    def test_cli_exit_codes_and_machine_readable_results(self):
        for scenario, code in (("outage", 0), ("retention-gap", 2)):
            with self.subTest(scenario=scenario):
                result = subprocess.run([sys.executable, str(ROOT / "replay_demo.py"), "--scenario", scenario], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, code)
                self.assertTrue(json.loads(result.stdout)["simulation"])


if __name__ == "__main__":
    unittest.main()

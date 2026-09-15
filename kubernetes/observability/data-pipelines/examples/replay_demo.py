"""Offline teaching model. No broker, search engine, table engine or network IO.

Rows have one producer/attempt per run. Integer sequence models source ordering;
it is not a global Kafka order or an authoritative production state machine.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

FIELDS = {"event_id", "run_id", "sequence", "state", "event_time", "bytes_completed"}


def load_events(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if number > 100_000 or len(line) > 65_536:
                raise ValueError("demo input exceeds its bound")
            if line.strip():
                rows.append(json.loads(line))
    validate(rows)
    return rows


def validate(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("empty event corpus")
    identities = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("unexpected event fields")
        for field in ("event_id", "run_id", "state", "event_time"):
            if not isinstance(row[field], str) or not row[field]:
                raise ValueError("invalid text field")
        for field in ("sequence", "bytes_completed"):
            if type(row[field]) is not int or row[field] < 0:
                raise ValueError("invalid numeric field")
        stamp = datetime.fromisoformat(row["event_time"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("event time must have a timezone")
        identity = row["event_id"]
        if identity in identities and identities[identity] != row:
            raise ValueError("conflicting duplicate event identity")
        identities[identity] = row


def simulate(rows: list[dict], scenario: str = "outage") -> dict:
    validate(rows)
    if scenario not in {"outage", "retention-gap"}:
        raise ValueError("unknown scenario")
    # Memory-only structures deliberately do not model real durability/checkpoints.
    source, hot, archive = [], {}, []
    hot_cursor = archive_cursor = 0
    retried = False
    pause_until = max(1, len(rows) // 2)
    hot_during_archive_pause = 0
    for tick, row in enumerate(rows):
        source.append(deepcopy(row))
        while hot_cursor < len(source):
            if hot_cursor == 3 and not retried:
                retried = True  # One synthetic rejection; do not advance cursor.
                break
            event = source[hot_cursor]
            hot[event["event_id"]] = deepcopy(event)
            hot_cursor += 1
        if tick < pause_until:
            hot_during_archive_pause = len(hot)
        if scenario == "outage" and tick >= pause_until:
            while archive_cursor < len(source):
                archive.append((archive_cursor, deepcopy(source[archive_cursor])))
                archive_cursor += 1
    while hot_cursor < len(source):
        event = source[hot_cursor]
        hot[event["event_id"]] = deepcopy(event)
        hot_cursor += 1
    earliest_available_offset = min(3, len(source)) if scenario == "retention-gap" else 0
    missing_offsets = list(range(archive_cursor, earliest_available_offset))
    if not missing_offsets:
        while archive_cursor < len(source):
            archive.append((archive_cursor, deepcopy(source[archive_cursor])))
            archive_cursor += 1
    arrival_state, sequence_state = {}, {}
    for row in rows:
        arrival_state[row["run_id"]] = row["state"]
        previous = sequence_state.get(row["run_id"])
        if previous is None or row["sequence"] > previous["sequence"]:
            sequence_state[row["run_id"]] = row
    source_ids = {row["event_id"] for row in rows}
    archive_ids = {row["event_id"] for _, row in archive}
    return {
        "simulation": True,
        "status": "retention_gap" if missing_offsets else "complete",
        "scenario": scenario,
        "source_records": len(source),
        "logical_events": len(source_ids),
        "duplicate_source_records": len(source) - len(source_ids),
        "hot_documents": len(hot),
        "archive_records": len(archive),
        "archive_logical_events": len(archive_ids),
        "hot_visible_during_archive_pause": hot_during_archive_pause,
        "hot_retry_was_simulated": retried,
        "archive_next_offset": archive_cursor,
        "earliest_available_source_offset": earliest_available_offset,
        "missing_source_offsets": missing_offsets,
        "logical_sink_sets_match": set(hot) == archive_ids == source_ids,
        "naive_arrival_state": arrival_state,
        "source_sequence_state": {key: row["state"] for key, row in sequence_state.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("events.jsonl"))
    parser.add_argument("--scenario", choices=("outage", "retention-gap"), default="outage")
    args = parser.parse_args()
    try:
        result = simulate(load_events(args.input), args.scenario)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"invalid demo input: {type(exc).__name__}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"] != "complete" else 0


if __name__ == "__main__":
    raise SystemExit(main())

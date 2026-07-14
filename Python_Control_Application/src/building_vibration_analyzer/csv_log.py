from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class Sample:
    timestamp_iso8601: str
    elapsed_us: int
    sample_number: int
    x_counts: int
    y_counts: int
    z_counts: int
    x_mps2: float
    y_mps2: float
    z_mps2: float
    temperature_c: float | None
    status_flags: str


@dataclass
class Session:
    session_id: str
    start_record: dict[str, str] | None = None
    end_record: dict[str, str] | None = None
    samples: list[Sample] = field(default_factory=list)
    events: list[dict[str, str]] = field(default_factory=list)
    faults: list[dict[str, str]] = field(default_factory=list)

    @property
    def sample_rate_hz(self) -> float | None:
        if len(self.samples) < 2:
            return None
        elapsed = [s.elapsed_us for s in self.samples]
        diffs = [(b - a) for a, b in zip(elapsed, elapsed[1:]) if b > a]
        if not diffs:
            return None
        median_us = sorted(diffs)[len(diffs) // 2]
        return 1_000_000.0 / median_us

    @property
    def duration_s(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return (self.samples[-1].elapsed_us - self.samples[0].elapsed_us) / 1_000_000.0


def _to_float(value: str) -> float:
    if value is None or value == "" or value.upper() == "NAN":
        return float("nan")
    return float(value)


def parse_sample(row: dict[str, str]) -> Sample | None:
    try:
        return Sample(
            timestamp_iso8601=row.get("timestamp_iso8601", "RTC_INVALID"),
            elapsed_us=int(row.get("elapsed_us") or 0),
            sample_number=int(row.get("sample_number") or 0),
            x_counts=int(row.get("x_counts") or 0),
            y_counts=int(row.get("y_counts") or 0),
            z_counts=int(row.get("z_counts") or 0),
            x_mps2=_to_float(row.get("x_mps2", "")),
            y_mps2=_to_float(row.get("y_mps2", "")),
            z_mps2=_to_float(row.get("z_mps2", "")),
            temperature_c=None if row.get("temperature_c", "") == "" else _to_float(row.get("temperature_c", "")),
            status_flags=row.get("status_flags", ""),
        )
    except (TypeError, ValueError):
        return None


def load_sessions(path: str | Path) -> list[Session]:
    sessions: dict[str, Session] = {}
    order: list[str] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            record_type = (row.get("record_type") or "").upper()
            session_id = row.get("session_id") or "unknown"
            if session_id not in sessions:
                sessions[session_id] = Session(session_id=session_id)
                order.append(session_id)
            session = sessions[session_id]
            if record_type == "SESSION_START":
                session.start_record = row
            elif record_type == "SESSION_END":
                session.end_record = row
            elif record_type == "DATA":
                sample = parse_sample(row)
                if sample is not None:
                    session.samples.append(sample)
            elif record_type == "FAULT":
                session.faults.append(row)
            elif record_type in {"EVENT", "META"}:
                session.events.append(row)
    return [sessions[sid] for sid in order]


def export_session_csv(session: Session, path: str | Path) -> None:
    fieldnames = [
        "timestamp_iso8601",
        "elapsed_us",
        "sample_number",
        "x_counts",
        "y_counts",
        "z_counts",
        "x_mps2",
        "y_mps2",
        "z_mps2",
        "temperature_c",
        "status_flags",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for sample in session.samples:
            writer.writerow(sample.__dict__)


def samples_to_arrays(samples: Iterable[Sample]):
    import numpy as np

    samples = list(samples)
    t = np.array([s.elapsed_us for s in samples], dtype=float) / 1_000_000.0
    if len(t):
        t -= t[0]
    data = {
        "x": np.array([s.x_mps2 for s in samples], dtype=float),
        "y": np.array([s.y_mps2 for s in samples], dtype=float),
        "z": np.array([s.z_mps2 for s in samples], dtype=float),
    }
    data["magnitude"] = np.sqrt(data["x"] ** 2 + data["y"] ** 2 + data["z"] ** 2)
    return t, data

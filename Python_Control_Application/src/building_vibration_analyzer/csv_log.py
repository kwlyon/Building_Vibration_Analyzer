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


def export_session_csv(
    session: Session,
    path: str | Path,
    time_window: tuple[float, float] | None = None,
) -> None:
    samples = select_samples_by_elapsed(session, *time_window) if time_window else list(session.samples)
    if not samples:
        raise ValueError("selected time window contains no samples")
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
        for sample in samples:
            writer.writerow(sample.__dict__)


def session_elapsed_seconds(samples: Iterable[Sample]):
    import numpy as np

    samples = list(samples)
    if not samples:
        return np.array([], dtype=float)
    base_us = samples[0].elapsed_us
    return np.array([(s.elapsed_us - base_us) / 1_000_000.0 for s in samples], dtype=float)


def normalize_elapsed_window(
    session: Session, start_s: float | None = None, end_s: float | None = None
) -> tuple[float, float]:
    duration = max(0.0, session.duration_s)
    start = 0.0 if start_s is None else float(start_s)
    end = duration if end_s is None else float(end_s)
    left, right = sorted((start, end))
    return max(0.0, min(duration, left)), max(0.0, min(duration, right))


def select_samples_by_elapsed(session: Session, start_s: float | None = None, end_s: float | None = None) -> list[Sample]:
    if not session.samples:
        return []
    start_s, end_s = normalize_elapsed_window(session, start_s, end_s)
    base_us = session.samples[0].elapsed_us
    selected: list[Sample] = []
    for sample in session.samples:
        elapsed_s = (sample.elapsed_us - base_us) / 1_000_000.0
        if elapsed_s < start_s:
            continue
        if elapsed_s > end_s:
            continue
        selected.append(sample)
    return selected


def sample_rate_from_samples(samples: Iterable[Sample]) -> float | None:
    samples = list(samples)
    if len(samples) < 2:
        return None
    diffs = [b.elapsed_us - a.elapsed_us for a, b in zip(samples, samples[1:]) if b.elapsed_us > a.elapsed_us]
    if not diffs:
        return None
    median_us = sorted(diffs)[len(diffs) // 2]
    return 1_000_000.0 / median_us


def samples_to_arrays(samples: Iterable[Sample]):
    import numpy as np

    samples = list(samples)
    t = session_elapsed_seconds(samples)
    data = {
        "x": np.array([s.x_mps2 for s in samples], dtype=float),
        "y": np.array([s.y_mps2 for s in samples], dtype=float),
        "z": np.array([s.z_mps2 for s in samples], dtype=float),
    }
    data["magnitude"] = np.sqrt(data["x"] ** 2 + data["y"] ** 2 + data["z"] ** 2)
    return t, data

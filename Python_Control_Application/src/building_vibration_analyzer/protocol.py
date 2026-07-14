from __future__ import annotations

from dataclasses import dataclass, field
import shlex
import zlib


@dataclass(frozen=True)
class ProtocolResponse:
    kind: str
    ok: bool
    command: str = ""
    code: str = ""
    message: str = ""
    fields: dict[str, str] = field(default_factory=dict)


def _parse_key_values(tokens: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value.strip('"')
    return fields


def parse_response_line(line: str) -> ProtocolResponse:
    """Parse one firmware response line."""
    stripped = line.strip()
    if not stripped:
        raise ValueError("empty response line")
    tokens = shlex.split(stripped)
    lead = tokens[0].upper()
    if lead == "OK":
        command = tokens[1].upper() if len(tokens) > 1 else ""
        return ProtocolResponse(
            kind="OK",
            ok=True,
            command=command,
            fields=_parse_key_values(tokens[2:]),
            message=" ".join(t for t in tokens[2:] if "=" not in t),
        )
    if lead == "ERR":
        code = tokens[1].upper() if len(tokens) > 1 else "UNKNOWN"
        return ProtocolResponse(
            kind="ERR",
            ok=False,
            code=code,
            message=" ".join(tokens[2:]),
            fields=_parse_key_values(tokens[2:]),
        )
    if lead == "EVT":
        event = tokens[1].upper() if len(tokens) > 1 else ""
        return ProtocolResponse(kind="EVT", ok=True, command=event, fields=_parse_key_values(tokens[2:]))
    if lead == "FILE":
        return ProtocolResponse(kind="FILE", ok=True, command="FILE", fields=_parse_key_values(tokens[1:]))
    if lead == "INFO":
        return ProtocolResponse(kind="INFO", ok=True, command="INFO", message=stripped[5:])
    return ProtocolResponse(kind=lead, ok=True, command=lead, message=" ".join(tokens[1:]))


def build_set_rtc_command(timestamp_iso8601: str) -> str:
    if not timestamp_iso8601.endswith("Z"):
        raise ValueError("RTC timestamp must be UTC and end with Z")
    return f"SET RTC {timestamp_iso8601}"


def build_set_rate_command(rate_hz: int) -> str:
    if rate_hz < 4 or rate_hz > 4000:
        raise ValueError("ADXL355 ODR must be between 4 and 4000 Hz")
    return f"SET RATE {rate_hz}"


def build_set_range_command(range_g: int) -> str:
    if range_g not in (2, 4, 8):
        raise ValueError("range must be 2, 4, or 8 g")
    return f"SET RANGE {range_g}"


def chunk_crc32(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def validate_chunk(data: bytes, expected_crc_hex: str) -> bool:
    return chunk_crc32(data).upper() == expected_crc_hex.upper()

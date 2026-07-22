from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Iterable

import serial
from serial.tools import list_ports

from .protocol import ProtocolResponse, parse_response_line


@dataclass(frozen=True)
class SerialPortInfo:
    device: str
    description: str
    hwid: str


class DeviceClient:
    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout
        self._serial: serial.Serial | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_stop = threading.Event()

    @staticmethod
    def list_ports() -> list[SerialPortInfo]:
        return [SerialPortInfo(p.device, p.description, p.hwid) for p in list_ports.comports()]

    def connect(self, port: str, baudrate: int = 115200) -> None:
        self.disconnect()
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=self.timeout, write_timeout=self.timeout)

    def disconnect(self) -> None:
        self.stop_reader()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def command(self, command: str, response_timeout: float | None = None) -> list[ProtocolResponse]:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("device is not connected")
        deadline = time.monotonic() + (response_timeout if response_timeout is not None else self.timeout)
        self._serial.write((command.rstrip() + "\n").encode("ascii"))
        self._serial.flush()
        responses: list[ProtocolResponse] = []
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            response = parse_response_line(text)
            responses.append(response)
            if response.kind in {"OK", "ERR"} and response.command not in {"LIST"}:
                break
            if response.kind.startswith("END"):
                break
        return responses

    def read_file_chunk_text(self, filename: str, offset: int = 0, length: int = 4096) -> bytes:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("device is not connected")
        self._serial.write(f"READ FILE {filename} {offset} {length}\n".encode("ascii"))
        self._serial.flush()

        first = self._serial.readline().decode("utf-8", errors="replace").strip()
        response = parse_response_line(first)
        if not response.ok:
            raise RuntimeError(first)
        if response.command != "READ":
            raise RuntimeError(f"unexpected file-read response: {first}")
        if "bytes" not in response.fields:
            raise RuntimeError("firmware does not support exact-byte downloads; upload the current firmware")
        try:
            payload_length = int(response.fields["bytes"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid file-read byte count: {first}") from exc
        if payload_length < 0 or payload_length > length:
            raise RuntimeError(f"invalid file-read byte count: {payload_length}")

        payload = bytearray()
        deadline = time.monotonic() + self.timeout
        while len(payload) < payload_length and time.monotonic() < deadline:
            block = self._serial.read(payload_length - len(payload))
            if block:
                payload.extend(block)
        if len(payload) != payload_length:
            raise RuntimeError(f"incomplete file chunk: expected {payload_length} bytes, received {len(payload)}")

        separator = self._serial.readline()
        end_marker = self._serial.readline()
        if separator not in {b"\n", b"\r\n"} or end_marker.strip() != b"END READ":
            raise RuntimeError("invalid file-read framing")
        return bytes(payload)

    def start_reader(self, callback: Callable[[str], None]) -> None:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("device is not connected")
        self.stop_reader()
        self._reader_stop.clear()

        def run() -> None:
            assert self._serial is not None
            while not self._reader_stop.is_set() and self._serial.is_open:
                raw = self._serial.readline()
                if raw:
                    callback(raw.decode("utf-8", errors="replace").rstrip())

        self._reader_thread = threading.Thread(target=run, name="bva-serial-reader", daemon=True)
        self._reader_thread.start()

    def stop_reader(self) -> None:
        self._reader_stop.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None

    def save_read_file_chunks(self, filename: str, destination: Path, chunk_size: int = 4096) -> None:
        offset = 0
        with destination.open("wb") as out:
            while True:
                payload = self.read_file_chunk_text(filename, offset, chunk_size)
                if not payload:
                    break
                out.write(payload)
                offset += len(payload)
                if len(payload) < chunk_size:
                    break


def likely_teensy_ports(ports: Iterable[SerialPortInfo]) -> list[SerialPortInfo]:
    needles = ("teensy", "pjrc", "usb serial", "ser")
    return [p for p in ports if any(n in f"{p.description} {p.hwid}".lower() for n in needles)]

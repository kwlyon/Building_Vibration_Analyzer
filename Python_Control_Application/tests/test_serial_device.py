import pathlib
import tempfile
import unittest

import serial

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.serial_device import DeviceClient


class FakeReadFileSerial:
    def __init__(self, source: bytes, include_byte_count: bool = True):
        self.source = source
        self.include_byte_count = include_byte_count
        self.is_open = True
        self._response = bytearray()

    def write(self, command: bytes) -> int:
        parts = command.decode("ascii").strip().split()
        offset = int(parts[-2])
        requested = int(parts[-1])
        payload = self.source[offset : offset + requested]
        header = f"OK READ name={parts[2]} offset={offset} length={requested}"
        if self.include_byte_count:
            header += f" bytes={len(payload)}"
        self._response.extend(header.encode("ascii") + b"\r\n" + payload + b"\r\nEND READ\r\n")
        return len(command)

    def flush(self) -> None:
        pass

    def read(self, size: int = 1) -> bytes:
        result = bytes(self._response[:size])
        del self._response[:size]
        return result

    def readline(self) -> bytes:
        try:
            end = self._response.index(b"\n") + 1
        except ValueError:
            return b""
        result = bytes(self._response[:end])
        del self._response[:end]
        return result


class SerialDownloadTests(unittest.TestCase):
    def make_client(self, source: bytes, include_byte_count: bool = True) -> DeviceClient:
        client = DeviceClient(timeout=0.1)
        client._serial = FakeReadFileSerial(source, include_byte_count)
        return client

    def test_chunk_preserves_embedded_newlines_and_marker_text(self):
        source = b"row-one\nEND READ\nrow-three-with-a-long-tail\n"
        client = self.make_client(source)
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "download.csv"
            client.save_read_file_chunks("VIBRATION_DATA.CSV", destination, chunk_size=7)
            self.assertEqual(destination.read_bytes(), source)

    def test_exact_multiple_of_chunk_size(self):
        source = b"01234567" * 4
        client = self.make_client(source)
        with tempfile.TemporaryDirectory() as tmp:
            destination = pathlib.Path(tmp) / "download.bin"
            client.save_read_file_chunks("DATA.BIN", destination, chunk_size=8)
            self.assertEqual(destination.read_bytes(), source)

    def test_old_firmware_is_rejected_instead_of_corrupting_file(self):
        client = self.make_client(b"sample data", include_byte_count=False)
        with self.assertRaisesRegex(RuntimeError, "current firmware"):
            client.read_file_chunk_text("VIBRATION_DATA.CSV", 0, 8)


if __name__ == "__main__":
    unittest.main()

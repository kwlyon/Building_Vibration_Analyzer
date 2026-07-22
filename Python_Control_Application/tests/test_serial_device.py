import pathlib
import tempfile
import unittest

import serial

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from building_vibration_analyzer.serial_device import DeviceClient, validate_remote_filename


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


class FakeCommandSerial:
    def __init__(self, response: bytes):
        self.is_open = True
        self._response = bytearray(response)
        self.commands = []

    def write(self, command: bytes) -> int:
        self.commands.append(command.decode("ascii").strip())
        return len(command)

    def flush(self) -> None:
        pass

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
            client.save_read_file_chunks("Data_0.csv", destination, chunk_size=7)
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
            client.read_file_chunk_text("Data_0.csv", 0, 8)

    def test_list_files_returns_multiple_remote_files(self):
        response = (
            b"OK LIST\r\n"
            b"FILE name=Data_0.csv size=123\r\n"
            b"FILE name=Data_4.csv size=456\r\n"
            b"END LIST\r\n"
        )
        client = DeviceClient(timeout=0.1)
        client._serial = FakeCommandSerial(response)
        files = client.list_files()
        self.assertEqual([(item.name, item.size) for item in files], [("Data_0.csv", 123), ("Data_4.csv", 456)])

    def test_delete_file_uses_validated_root_filename(self):
        client = DeviceClient(timeout=0.1)
        fake = FakeCommandSerial(b"OK DELETE name=Data_4.csv\r\n")
        client._serial = fake
        client.delete_file("Data_4.csv")
        self.assertEqual(fake.commands, ["DELETE FILE Data_4.csv"])

    def test_unsafe_remote_filenames_are_rejected(self):
        for name in ("../secret.csv", "folder/data.csv", "..", "bad name.csv", "C:\\data.csv"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_remote_filename(name)


if __name__ == "__main__":
    unittest.main()

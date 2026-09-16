import io
import zipfile

import pytest

from app.services.zip_ingest import ZipError, extract_zip, validate_zip_bytes


def _make_zip(entries: dict[str, bytes], symlink: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            if symlink:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (0o120777 << 16)
                zf.writestr(info, content)
            else:
                zf.writestr(name, content)
    return buf.getvalue()


def _set_encryption_bit(data: bytes) -> bytes:
    out = bytearray(data)
    i = out.find(b"PK\x03\x04")
    while i != -1:
        out[i + 6] |= 0x1
        i = out.find(b"PK\x03\x04", i + 1)
    i = out.find(b"PK\x01\x02")
    while i != -1:
        out[i + 8] |= 0x1
        i = out.find(b"PK\x01\x02", i + 1)
    return bytes(out)


def test_valid_zip_accepted():
    data = _make_zip({"app/main.py": "print('hi')\n"})
    validate_zip_bytes(data)


def test_empty_bytes_rejected():
    with pytest.raises(ZipError, match="empty"):
        validate_zip_bytes(b"")


def test_non_zip_rejected():
    with pytest.raises(ZipError, match="not a valid zip"):
        validate_zip_bytes(b"PK\x03\x04 not really a zip but long enough to pass" + b"\x00" * 100)


def test_plain_text_rejected():
    with pytest.raises(ZipError, match="not a valid zip"):
        validate_zip_bytes(b"hello world this is not a zip file at all")


def test_oversized_zip_rejected(monkeypatch):
    monkeypatch.setattr("app.services.zip_ingest.MAX_ZIP_BYTES", 1024 * 1024)
    data = _make_zip({"big.bin": b"x" * (2 * 1024 * 1024)})
    with pytest.raises(ZipError, match="MAX_ZIP_MB"):
        validate_zip_bytes(data)


def test_encrypted_zip_rejected():
    data = _set_encryption_bit(_make_zip({"secret.txt": "data"}))
    with pytest.raises(ZipError, match="encrypted"):
        validate_zip_bytes(data)


def test_extract_zip_basic(tmp_path):
    zip_path = tmp_path / "p.zip"
    zip_path.write_bytes(_make_zip({"app/main.py": "x=1\n", "app/readme.txt": "hi"}))
    dest = tmp_path / "out"
    count = extract_zip(zip_path, dest)
    assert count == 2
    assert (dest / "app" / "main.py").read_text() == "x=1\n"


def test_extract_zip_slip_absolute_rejected(tmp_path):
    zip_path = tmp_path / "p.zip"
    zip_path.write_bytes(_make_zip({"/etc/passwd": "root:x:0:0\n"}))
    dest = tmp_path / "out"
    with pytest.raises(ZipError, match="unsafe|escapes"):
        extract_zip(zip_path, dest)


def test_extract_zip_slip_dotdot_rejected(tmp_path):
    zip_path = tmp_path / "p.zip"
    zip_path.write_bytes(_make_zip({"../../evil.txt": "boom"}))
    dest = tmp_path / "out"
    with pytest.raises(ZipError, match="unsafe|escapes"):
        extract_zip(zip_path, dest)


def test_extract_zip_symlink_rejected(tmp_path):
    zip_path = tmp_path / "p.zip"
    zip_path.write_bytes(_make_zip({"link": "target"}, symlink=True))
    dest = tmp_path / "out"
    with pytest.raises(ZipError, match="symlink"):
        extract_zip(zip_path, dest)
import io
import zipfile
from pathlib import Path

from app.config import settings

MAX_ZIP_BYTES = settings.MAX_ZIP_MB * 1024 * 1024
MAX_ZIP_ENTRIES = settings.MAX_ZIP_ENTRIES


class ZipError(Exception):
    pass


def validate_zip_bytes(data: bytes) -> None:
    if not data:
        raise ZipError("uploaded file is empty")
    if len(data) > MAX_ZIP_BYTES:
        raise ZipError(f"zip file exceeds MAX_ZIP_MB ({settings.MAX_ZIP_MB} MB)")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ZipError("uploaded file is not a valid zip archive")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            if len(zf.infolist()) > MAX_ZIP_ENTRIES:
                raise ZipError(f"zip archive exceeds MAX_ZIP_ENTRIES ({MAX_ZIP_ENTRIES})")
            for info in zf.infolist():
                if info.flag_bits & 0x1:
                    raise ZipError("encrypted zip archives are not supported")
    except zipfile.BadZipFile as exc:
        raise ZipError(f"invalid zip archive: {exc}")


def extract_zip(zip_path: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if not name:
                continue
            norm = Path(name)
            if norm.is_absolute() or ".." in norm.parts:
                raise ZipError(f"zip entry has an unsafe path: {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ZipError(f"zip entry is a symlink: {name}")
            target = (dest / norm).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise ZipError(f"zip entry escapes the extraction directory: {name}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                out.write(src.read())
            extracted += 1
    return extracted
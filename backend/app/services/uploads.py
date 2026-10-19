"""Safe file uploads: size/type limits, magic-byte checks, random storage names, no executables."""
import hashlib
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import get_settings

ALLOWED = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG", "application/pdf": b"%PDF", "text/plain": None}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf", "text/plain": ".txt"}


async def read_validated(file: UploadFile, allowed: set[str] | None = None) -> tuple[bytes, str]:
    s = get_settings()
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, detail={"code": "file_too_large", "message": f"Max file size is {s.max_upload_mb} MB."})
    if not data:
        raise HTTPException(422, detail={"code": "empty_file", "message": "The file is empty."})
    ctype = (file.content_type or "").split(";")[0].strip()
    allowed = allowed or set(ALLOWED)
    if ctype not in allowed:
        raise HTTPException(415, detail={"code": "unsupported_type", "message": f"Allowed types: {', '.join(sorted(allowed))}."})
    magic = ALLOWED[ctype]
    if magic and not data.startswith(magic):
        raise HTTPException(415, detail={"code": "type_mismatch", "message": "File content does not match its type."})
    if ctype == "text/plain":
        if b"\x00" in data:
            raise HTTPException(415, detail={"code": "type_mismatch", "message": "Binary content in a text file."})
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, detail={"code": "bad_encoding", "message": "Text files must be UTF-8."}) from exc
    return data, ctype


def store(data: bytes, ctype: str) -> tuple[str, str]:
    d = Path(get_settings().upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(16) + EXT[ctype]
    (d / name).write_bytes(data)
    return name, hashlib.sha256(data).hexdigest()


def path_for(storage_name: str) -> Path:
    p = (Path(get_settings().upload_dir) / storage_name).resolve()
    if p.parent != Path(get_settings().upload_dir).resolve():
        raise HTTPException(400, detail={"code": "bad_path", "message": "Invalid file reference."})
    return p


def safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    return "".join(c for c in base if c.isalnum() or c in "._- ")[:120] or "upload"

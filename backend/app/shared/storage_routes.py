"""Signed upload/download endpoints for the local storage backend (development and tests only).

They mirror S3 semantics: the upload form carries a signed policy (key, content type, maximum size, expiry) and
downloads use expiring signed URLs. No bearer token is needed, exactly like a presigned S3 URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile

from app.core.errors import AppError, NotFound
from app.shared.storage import LocalStorage, content_disposition, get_storage, verify_payload

router = APIRouter(prefix="/storage/local", tags=["storage"], include_in_schema=False)

UPLOAD_PATH = "/api/v1/storage/local/upload"
_FORM_OVERHEAD = 64 * 1024


def _local() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise NotFound("Not found")
    return storage


@router.post("/upload", status_code=204)
async def upload(request: Request) -> Response:
    storage = _local()
    declared = request.headers.get("content-length")
    if not declared or not declared.isdigit():
        raise AppError("Content-Length is required", code="length_required", status_code=411)
    # Cheap pre-check before parsing: the hard per-file limit comes from the signed policy below.
    if int(declared) > 600 * 1024 * 1024:
        raise AppError("File too large", code="payload_too_large", status_code=413)
    form = await request.form(max_files=1, max_fields=10)
    try:
        policy = verify_payload(str(form.get("policy") or ""), purpose="upload")
        if policy is None:
            raise AppError("Upload policy is invalid or has expired", code="upload_policy_invalid", status_code=403)
        if int(declared) > int(policy["max"]) + _FORM_OVERHEAD:
            raise AppError("File too large", code="payload_too_large", status_code=413)
        if form.get("Content-Type") != policy["ct"]:
            raise AppError("Content-Type does not match the upload policy", code="upload_policy_invalid",
                           status_code=403)
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise AppError("A file field is required", code="validation_error", status_code=400)
        data = await file.read(int(policy["max"]) + 1)
        if not data:
            raise AppError("The file is empty", code="validation_error", status_code=400)
        if len(data) > int(policy["max"]):
            raise AppError("File too large", code="payload_too_large", status_code=413)
        await storage.write(policy["k"], data, policy["ct"])
    finally:
        await form.close()
    return Response(status_code=204)


@router.get("/files/{token}")
async def download(token: str) -> Response:
    storage = _local()
    payload = verify_payload(token, purpose="download")
    if payload is None:
        raise AppError("This link is invalid or has expired", code="download_link_invalid", status_code=403)
    path = storage.path_for(payload["k"])
    if not path.is_file():
        raise NotFound("File not found")
    return FileResponse(path, media_type=payload["ct"], headers={
        "Content-Disposition": content_disposition(payload["fn"], bool(payload["in"])),
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; sandbox",
        "Cache-Control": "private, max-age=300",
    })

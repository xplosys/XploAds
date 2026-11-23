"""Brand asset uploads: signed policies, server-side verification, signed downloads, deletion, cleanup."""

from __future__ import annotations

import io
import time

import pytest

from tests.conftest import create_org, owner_query, register
from tests.test_brand import make_brand, th


def png_bytes(w: int = 64, h: int = 32) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 163, 163)).save(buf, format="PNG")
    return buf.getvalue()


async def start(client, user, org, brand, *, kind="logo", filename="logo.png", size=None, **extra):
    body = {"brand_id": brand["id"], "kind": kind, "filename": filename, "content_type": "image/png",
            "size_bytes": size or 1000, **extra}
    return await client.post("/api/v1/assets/uploads", json=body, headers=th(user, org))


async def post_file(client, upload: dict, data: bytes, filename="logo.png"):
    return await client.post(upload["url"], data=upload["fields"], files={"file": (filename, data)})


async def upload(client, user, org, brand, data: bytes, **kw) -> dict:
    r = await start(client, user, org, brand, size=len(data), **kw)
    assert r.status_code == 201, r.text
    up = r.json()
    assert up["asset"]["status"] == "pending"
    r = await post_file(client, up["upload"], data, kw.get("filename", "logo.png"))
    assert r.status_code == 204, r.text
    r = await client.post(f"/api/v1/assets/{up['asset']['id']}/complete", headers=th(user, org))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
async def setup(client):
    u = await register(client)
    org = await create_org(client, u)
    brand = await make_brand(client, u, org)
    return u, org, brand


async def test_upload_logo_end_to_end(client, setup):
    u, org, brand = setup
    data = png_bytes()
    asset = await upload(client, u, org, brand, data, title="Primary logo")
    assert asset["status"] == "ready" and asset["mime_type"] == "image/png"
    assert (asset["width"], asset["height"]) == (64, 32) and asset["size_bytes"] == len(data)
    assert len(asset["checksum_sha256"]) == 64 and asset["title"] == "Primary logo"
    key = owner_query("SELECT storage_key FROM brand_assets WHERE id = %s", asset["id"])[0][0]
    assert key.startswith(f"tenants/{org['id']}/brands/{brand['id']}/assets/{asset['id']}/")

    # signed download serves the bytes with safe headers
    r = await client.get(asset["url"])
    assert r.status_code == 200 and r.content == data
    assert r.headers["content-type"] == "image/png" and r.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in r.headers["content-security-policy"]

    # complete is idempotent; listing shows it; set as brand logo
    again = await client.post(f"/api/v1/assets/{asset['id']}/complete", headers=th(u, org))
    assert again.json()["status"] == "ready"
    listed = (await client.get(f"/api/v1/brands/{brand['id']}/assets", headers=th(u, org))).json()
    assert listed["total"] == 1
    r = await client.patch(f"/api/v1/brands/{brand['id']}", json={"logo_asset_id": asset["id"]}, headers=th(u, org))
    assert r.status_code == 200 and r.json()["logo_url"]
    assert (await client.get("/api/v1/brands", headers=th(u, org))).json()[0]["logo_url"]

    # product image
    r = await client.post(f"/api/v1/brands/{brand['id']}/products", headers=th(u, org),
                          json={"name": "Kit", "image_asset_id": asset["id"]})
    assert r.status_code == 201 and r.json()["image_url"]

    # metadata
    r = await client.patch(f"/api/v1/assets/{asset['id']}", headers=th(u, org),
                           json={"tags": ["Logo", "logo", " primary "], "alt_text": "Acme logo",
                                 "rights_source": "licensed", "rights_notes": "Agency licence #42"})
    assert r.status_code == 200 and r.json()["tags"] == ["logo", "primary"]

    # delete clears references and queues object removal for the worker
    assert (await client.delete(f"/api/v1/assets/{asset['id']}", headers=th(u, org))).status_code == 200
    assert (await client.get(f"/api/v1/brands/{brand['id']}", headers=th(u, org))).json()["logo_asset_id"] is None
    events = owner_query(
        "SELECT payload->>'key' FROM outbox_events WHERE event_type = 'storage.object_delete_requested'")
    assert events == [(key,)]
    from app.shared.outbox import OutboxEvent
    from app.workers.handlers import delete_stored_object

    await delete_stored_object(OutboxEvent(event_type="x", payload={"key": key}, tenant_id=org["id"]))
    assert (await client.get(asset["url"])).status_code == 404
    with pytest.raises(ValueError):
        await delete_stored_object(OutboxEvent(event_type="x", payload={"key": "tenants/other/x"},
                                               tenant_id=org["id"]))


async def test_rejects_disallowed_types_and_sizes(client, setup):
    u, org, brand = setup
    r = await start(client, u, org, brand, filename="logo.svg")
    assert r.status_code == 400 and r.json()["error"]["code"] == "file_type_not_allowed"
    r = await start(client, u, org, brand, filename="run.exe", kind="document")
    assert r.status_code == 400
    r = await start(client, u, org, brand, filename="noext")
    assert r.status_code == 400
    r = await start(client, u, org, brand, size=6 * 1024 * 1024)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    r = await start(client, u, org, brand, kind="banner")
    assert r.status_code == 422


async def test_spoofed_content_is_rejected_and_removed(client, setup):
    u, org, brand = setup
    html = b"<html><script>alert(1)</script></html>"
    asset = await upload(client, u, org, brand, html)
    assert asset["status"] == "rejected" and "does not match" in asset["rejection_reason"]
    assert asset["url"] is None
    assert owner_query("SELECT count(*) FROM outbox_events WHERE event_type = 'storage.object_delete_requested'"
                       ) == [(1,)]
    # rejected assets cannot be completed again or used as a logo
    r = await client.post(f"/api/v1/assets/{asset['id']}/complete", headers=th(u, org))
    assert r.json()["error"]["code"] == "upload_rejected"
    r = await client.patch(f"/api/v1/brands/{brand['id']}", json={"logo_asset_id": asset["id"]}, headers=th(u, org))
    assert r.status_code == 400 and r.json()["error"]["code"] == "asset_not_usable"
    # a PNG header followed by garbage passes sniffing but fails full decoding
    broken = png_bytes()[:40] + b"\x00" * 200
    asset = await upload(client, u, org, brand, broken)
    assert asset["status"] == "rejected" and "could not be read" in asset["rejection_reason"]


async def test_upload_policy_is_enforced(client, setup):
    u, org, brand = setup
    data = png_bytes()
    up = (await start(client, u, org, brand, size=len(data))).json()["upload"]
    # tampered policy
    bad = {**up["fields"], "policy": up["fields"]["policy"][:-2] + "AA"}
    r = await client.post(up["url"], data=bad, files={"file": ("logo.png", data)})
    assert r.status_code == 403
    # content type must match the signed one
    r = await client.post(up["url"], data={**up["fields"], "Content-Type": "text/html"},
                          files={"file": ("logo.png", data)})
    assert r.status_code == 403
    # larger than the kind's limit, even though the policy itself is valid
    from app.modules.brand.services.rules import RULES

    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * RULES["logo"].max_bytes
    r = await client.post(up["url"], data=up["fields"], files={"file": ("logo.png", big)})
    assert r.status_code == 413
    # empty file
    r = await client.post(up["url"], data=up["fields"], files={"file": ("logo.png", b"")})
    assert r.status_code == 400


async def test_expired_and_tampered_download_links(client, setup, monkeypatch):
    u, org, brand = setup
    asset = await upload(client, u, org, brand, png_bytes())
    token = asset["url"].rsplit("/", 1)[1]
    assert (await client.get(asset["url"][:-3] + "abc")).status_code == 403
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 3600)
    assert (await client.get(f"/api/v1/storage/local/files/{token}")).status_code == 403


async def test_incomplete_upload_and_permissions(client, setup):
    u, org, brand = setup
    up = (await start(client, u, org, brand)).json()
    r = await client.post(f"/api/v1/assets/{up['asset']['id']}/complete", headers=th(u, org))
    assert r.status_code == 400 and r.json()["error"]["code"] == "upload_incomplete"
    # pending uploads are hidden from the library by default
    assert (await client.get(f"/api/v1/brands/{brand['id']}/assets", headers=th(u, org))).json()["total"] == 0
    pending = (await client.get(f"/api/v1/brands/{brand['id']}/assets?status=pending", headers=th(u, org))).json()
    assert pending["total"] == 1
    # another tenant cannot complete, read or delete it
    other = await register(client)
    org2 = await create_org(client, other, "Other")
    for method, path in [("POST", f"/api/v1/assets/{up['asset']['id']}/complete"),
                         ("GET", f"/api/v1/assets/{up['asset']['id']}"),
                         ("DELETE", f"/api/v1/assets/{up['asset']['id']}"),
                         ("GET", f"/api/v1/assets/{up['asset']['id']}/download")]:
        assert (await client.request(method, path, headers=th(other, org2))).status_code == 404


async def test_cleanup_rejects_stale_pending_uploads(client, setup):
    u, org, brand = setup
    up = (await start(client, u, org, brand)).json()
    owner_query("UPDATE brand_assets SET upload_expires_at = now() - interval '2 hours' WHERE id = %s",
                up["asset"]["id"])
    from app.core.database import get_sessionmaker
    from app.modules.brand.services.assets import cleanup_stale_uploads

    async with get_sessionmaker()() as s, s.begin():
        assert await cleanup_stale_uploads(s) == 1
    row = owner_query("SELECT status, deleted_at IS NOT NULL FROM brand_assets WHERE id = %s", up["asset"]["id"])
    assert row == [("rejected", True)]


async def test_s3_backend_presign_and_verify(client, setup, monkeypatch):
    """Same flow against an S3 API (moto), as used with AWS S3, Cloudflare R2 or MinIO."""
    moto = pytest.importorskip("moto")
    u, org, brand = setup
    with moto.mock_aws():
        from app.core.config import get_settings
        from app.shared.storage import S3Storage

        s = get_settings()
        monkeypatch.setattr(s, "storage_backend", "s3")
        monkeypatch.setattr(s, "s3_endpoint_url", None)
        monkeypatch.setattr(s, "s3_access_key_id", "test")
        monkeypatch.setattr(s, "s3_secret_access_key", "test")
        storage = S3Storage()
        storage.ensure_bucket()
        import app.modules.brand.services.assets as assets_mod

        monkeypatch.setattr(assets_mod, "get_storage", lambda: storage)

        data = png_bytes(20, 10)
        up = (await start(client, u, org, brand, size=len(data))).json()
        fields = up["upload"]["fields"]
        assert fields["Content-Type"] == "image/png" and "policy" in fields and fields["key"].startswith(
            f"tenants/{org['id']}/")
        storage._client.put_object(Bucket=s.storage_bucket, Key=fields["key"], Body=data, ContentType="image/png")
        asset = (await client.post(f"/api/v1/assets/{up['asset']['id']}/complete", headers=th(u, org))).json()
        assert asset["status"] == "ready" and asset["width"] == 20
        assert "X-Amz-Signature" in asset["url"] and "response-content-disposition=inline" in asset["url"]

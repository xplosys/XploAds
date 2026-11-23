"""Brand profiles, guidelines, products/services and organization profile settings."""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import create_org, latest_event_token, owner_query, register, unique_email


def th(user: dict, org: dict) -> dict:
    return {**user["headers"], "X-Tenant-ID": org["id"]}


async def make_brand(client, user, org, name="Acme Dental", **extra) -> dict:
    r = await client.post("/api/v1/brands", json={"name": name, **extra}, headers=th(user, org))
    assert r.status_code == 201, r.text
    return r.json()


async def add_member(client, owner, org, role_key: str) -> dict:
    email = unique_email(role_key)
    r = await client.post(f"/api/v1/organizations/{org['id']}/members", json={"email": email, "role_key": role_key},
                          headers=owner["headers"])
    assert r.status_code == 201, r.text
    invite_token = latest_event_token("tenant.invitation_created", email)
    member = await register(client, email=email)
    r = await client.post("/api/v1/invitations/accept", json={"token": invite_token}, headers=member["headers"])
    assert r.status_code == 200, r.text
    return member


async def test_brand_crud_and_default(client):
    u = await register(client)
    org = await create_org(client, u)
    first = await make_brand(client, u, org, tagline="Smiles that last", website="https://acme.example",
                             colors=[{"name": "Teal", "hex": "#0aa3a3", "usage": "primary"}],
                             fonts=[{"family": "Inter", "usage": "body"}],
                             value_propositions=["Same-day appointments", "Painless care"],
                             social_links={"instagram": "https://instagram.com/acme"})
    assert first["is_default"] is True and first["slug"] == "acme-dental"
    assert first["colors"][0]["hex"] == "#0AA3A3"
    assert first["website"] == "https://acme.example/"
    second = await make_brand(client, u, org, name="Acme Dental")
    assert second["slug"] == "acme-dental-2" and second["is_default"] is False

    r = await client.patch(f"/api/v1/brands/{second['id']}", headers=th(u, org),
                           json={"tone_of_voice": "Warm, reassuring, plain English", "colors": []})
    assert r.status_code == 200 and r.json()["tone_of_voice"].startswith("Warm") and r.json()["colors"] == []

    # cannot archive the default brand; switch default first
    r = await client.patch(f"/api/v1/brands/{first['id']}", json={"status": "archived"}, headers=th(u, org))
    assert r.status_code == 400 and r.json()["error"]["code"] == "brand_is_default"
    assert (await client.post(f"/api/v1/brands/{second['id']}/default", headers=th(u, org))).status_code == 200
    r = await client.patch(f"/api/v1/brands/{first['id']}", json={"status": "archived"}, headers=th(u, org))
    assert r.status_code == 200
    names = [b["id"] for b in (await client.get("/api/v1/brands", headers=th(u, org))).json()]
    assert names == [second["id"]]
    all_ = (await client.get("/api/v1/brands?include_archived=true", headers=th(u, org))).json()
    assert len(all_) == 2

    # delete the (default) brand; the only other one is archived, so it is not promoted
    assert (await client.delete(f"/api/v1/brands/{second['id']}", headers=th(u, org))).status_code == 200
    assert (await client.get(f"/api/v1/brands/{second['id']}", headers=th(u, org))).status_code == 404
    actions = {a for (a,) in owner_query("SELECT action FROM audit_logs WHERE tenant_id = %s", org["id"])}
    assert {"brand.created", "brand.updated", "brand.default_changed", "brand.deleted"} <= actions


async def test_brand_validation(client):
    u = await register(client)
    org = await create_org(client, u)
    h = th(u, org)
    bad = [
        {"name": "x"},
        {"name": "Ok brand", "colors": [{"name": "Bad", "hex": "red"}]},
        {"name": "Ok brand", "social_links": {"myspace": "https://myspace.com/x"}},
        {"name": "Ok brand", "website": "javascript:alert(1)"},
        {"name": "Ok brand", "value_propositions": ["v"] * 21},
    ]
    for body in bad:
        r = await client.post("/api/v1/brands", json=body, headers=h)
        assert r.status_code == 422, body
    # header is mandatory and must be a UUID the user belongs to
    assert (await client.get("/api/v1/brands", headers=u["headers"])).json()["error"]["code"] == "tenant_required"
    r = await client.get("/api/v1/brands", headers={**u["headers"], "X-Tenant-ID": str(uuid.uuid4())})
    assert r.status_code == 404


async def test_guidelines(client):
    u = await register(client)
    org = await create_org(client, u)
    b = await make_brand(client, u, org)
    base = f"/api/v1/brands/{b['id']}/guidelines"
    g1 = (await client.post(base, headers=th(u, org), json={"category": "voice", "title": "Tone",
                                                            "content": "Friendly", "sort_order": 2})).json()
    await client.post(base, headers=th(u, org), json={"category": "dont", "title": "No jargon",
                                                      "content": "Avoid clinical terms", "sort_order": 1})
    listed = (await client.get(base, headers=th(u, org))).json()
    assert [g["title"] for g in listed] == ["No jargon", "Tone"]
    r = await client.patch(f"{base}/{g1['id']}", json={"content": "Friendly and calm"}, headers=th(u, org))
    assert r.status_code == 200 and r.json()["content"] == "Friendly and calm"
    assert (await client.post(base, headers=th(u, org), json={"category": "nope", "title": "t",
                                                              "content": "c"})).status_code == 422
    assert (await client.delete(f"{base}/{g1['id']}", headers=th(u, org))).status_code == 200
    detail = (await client.get(f"/api/v1/brands/{b['id']}", headers=th(u, org))).json()
    assert detail["counts"]["guidelines"] == 1


async def test_products_and_services(client):
    u = await register(client)
    org = await create_org(client, u)  # default currency USD
    b = await make_brand(client, u, org)
    base = f"/api/v1/brands/{b['id']}/products"
    p = await client.post(base, headers=th(u, org), json={
        "name": "Teeth whitening", "kind": "service", "price": "149.50", "features": ["45 minutes", "Take-home kit"]})
    assert p.status_code == 201, p.text
    p = p.json()
    assert p["price"] == "149.50" and p["currency"] == "USD" and p["kind"] == "service"
    await client.post(base, headers=th(u, org), json={"name": "Electric toothbrush", "sku": "TB-1", "price": "59",
                                                      "currency": "INR"})
    dup = await client.post(base, headers=th(u, org), json={"name": "Copy", "sku": "TB-1"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "sku_taken"
    assert (await client.post(base, headers=th(u, org), json={"name": "Neg", "price": "-1"})).status_code == 422
    assert (await client.post(base, headers=th(u, org), json={"name": "Frac", "price": "1.234"})).status_code == 422

    page = (await client.get(f"{base}?kind=service", headers=th(u, org))).json()
    assert page["total"] == 1 and page["items"][0]["name"] == "Teeth whitening"
    page = (await client.get(f"{base}?q=tooth", headers=th(u, org))).json()
    assert [i["sku"] for i in page["items"]] == ["TB-1"]
    page = (await client.get(f"{base}?q=%25", headers=th(u, org))).json()
    assert page["total"] == 0  # % is matched literally, not as a wildcard

    r = await client.patch(f"/api/v1/products/{p['id']}", json={"status": "archived", "price": None},
                           headers=th(u, org))
    assert r.status_code == 200 and r.json()["status"] == "archived" and r.json()["price"] is None
    assert (await client.delete(f"/api/v1/products/{p['id']}", headers=th(u, org))).status_code == 200
    assert (await client.get(f"/api/v1/products/{p['id']}", headers=th(u, org))).status_code == 404


@pytest.mark.parametrize(("role", "can_read", "can_manage"), [
    ("viewer", True, False), ("member", True, True), ("manager", True, True), ("sales", False, False),
    ("billing_admin", False, False),
])
async def test_brand_permissions_by_role(client, role, can_read, can_manage):
    owner = await register(client)
    org = await create_org(client, owner)
    brand = await make_brand(client, owner, org)
    m = await add_member(client, owner, org, role)
    r = await client.get(f"/api/v1/brands/{brand['id']}", headers=th(m, org))
    assert r.status_code == (200 if can_read else 403)
    r = await client.post("/api/v1/brands", json={"name": "New brand"}, headers=th(m, org))
    assert r.status_code == (201 if can_manage else 403)
    r = await client.post(f"/api/v1/brands/{brand['id']}/products", json={"name": "P"}, headers=th(m, org))
    assert r.status_code == (201 if can_manage else 403)


async def test_cross_tenant_brand_access_is_404(client):
    a, b = await register(client), await register(client)
    org_a, org_b = await create_org(client, a, "Alpha"), await create_org(client, b, "Beta")
    brand_b = await make_brand(client, b, org_b, "Beta Brand")
    prod_b = (await client.post(f"/api/v1/brands/{brand_b['id']}/products", json={"name": "Secret"},
                                headers=th(b, org_b))).json()
    # A cannot use B's tenant at all
    assert (await client.get("/api/v1/brands", headers=th(a, org_b))).status_code == 404
    # nor reach B's objects through A's own tenant
    for method, path, body in [
        ("GET", f"/api/v1/brands/{brand_b['id']}", None),
        ("PATCH", f"/api/v1/brands/{brand_b['id']}", {"name": "pwned"}),
        ("DELETE", f"/api/v1/brands/{brand_b['id']}", None),
        ("GET", f"/api/v1/brands/{brand_b['id']}/guidelines", None),
        ("POST", f"/api/v1/brands/{brand_b['id']}/products", {"name": "x"}),
        ("GET", f"/api/v1/products/{prod_b['id']}", None),
        ("PATCH", f"/api/v1/products/{prod_b['id']}", {"name": "pwned"}),
        ("POST", "/api/v1/assets/uploads", {"brand_id": brand_b["id"], "kind": "logo", "filename": "a.png",
                                           "content_type": "image/png", "size_bytes": 10}),
    ]:
        r = await client.request(method, path, json=body, headers=th(a, org_a))
        assert r.status_code == 404, (method, path, r.text)
    assert owner_query("SELECT name FROM brand_profiles WHERE id = %s", brand_b["id"]) == [("Beta Brand",)]


async def test_agency_manages_client_brand_with_audit(client):
    owner = await register(client)
    agency = await create_org(client, owner, "Growth Agency", "agency")
    r = await client.post(f"/api/v1/organizations/{agency['id']}/clients", json={"name": "Client Co"},
                          headers=owner["headers"])
    cli = r.json()
    brand = await make_brand(client, owner, cli, "Client Brand")
    assert brand["is_default"]
    rows = owner_query("SELECT metadata->>'via' FROM audit_logs WHERE tenant_id = %s AND action = 'brand.created'",
                       cli["id"])
    assert rows == [("agency",)]
    # agency viewers lack agency.clients.access, so client tenants are invisible to them
    viewer = await add_member(client, owner, agency, "viewer")
    assert (await client.get("/api/v1/brands", headers=th(viewer, cli))).status_code == 404


async def test_organization_profile_fields(client):
    u = await register(client)
    org = await create_org(client, u)
    r = await client.patch(f"/api/v1/organizations/{org['id']}", headers=u["headers"], json={
        "description": "Family dental clinic", "contact_email": "Hello@Acme.Example",
        "contact_phone": "+91 98765 43210", "address": "12 MG Road, Bengaluru", "name": None})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contact_email"] == "hello@acme.example" and body["name"] == "Acme Dental"
    assert body["description"] == "Family dental clinic"
    bad = await client.patch(f"/api/v1/organizations/{org['id']}", headers=u["headers"],
                             json={"contact_phone": "<script>"})
    assert bad.status_code == 422

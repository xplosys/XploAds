from __future__ import annotations

from tests.conftest import create_org, latest_event_token, owner_query, register, unique_email


async def _invite_and_accept(client, owner, org_id, role="member"):
    email = unique_email("invitee")
    r = await client.post(f"/api/v1/organizations/{org_id}/members", headers=owner["headers"],
                          json={"email": email, "role_key": role})
    assert r.status_code == 201, r.text
    token = latest_event_token("tenant.invitation_created", email)
    invitee = await register(client, email=email, verify=False)
    acc = await client.post("/api/v1/invitations/accept", json={"token": token}, headers=invitee["headers"])
    assert acc.status_code == 200, acc.text
    return invitee


async def test_create_organization_makes_owner_and_default_workspace(client):
    u = await register(client)
    org = await create_org(client, u, "Sunrise Clinic")
    assert org["tenant_type"] == "business" and org["slug"].startswith("sunrise-clinic-")
    orgs = (await client.get("/api/v1/organizations", headers=u["headers"])).json()
    assert len(orgs) == 1 and orgs[0]["roles"] == ["owner"] and "members.invite" in orgs[0]["permissions"]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=u["headers"])).json()
    assert [w["slug"] for w in ws] == ["general"] and ws[0]["is_default"]
    audit = (await client.get(f"/api/v1/organizations/{org['id']}/audit-logs", headers=u["headers"])).json()
    assert audit["items"][0]["action"] == "organization.created"


async def test_client_type_cannot_be_created_directly(client):
    u = await register(client)
    r = await client.post("/api/v1/organizations", json={"name": "X Corp", "tenant_type": "client"},
                          headers=u["headers"])
    assert r.status_code == 422


async def test_invitation_flow_and_role_permissions(client):
    owner = await register(client)
    org = await create_org(client, owner)
    viewer = await _invite_and_accept(client, owner, org["id"], role="viewer")
    me = (await client.get("/api/v1/auth/me", headers=viewer["headers"])).json()
    assert me["email_verified"] is True  # accepting the emailed invitation proves the mailbox
    members = (await client.get(f"/api/v1/organizations/{org['id']}/members", headers=owner["headers"])).json()
    assert {m["roles"][0]["role_key"] for m in members} == {"owner", "viewer"}
    # viewer can read but not invite or edit
    assert (await client.get(f"/api/v1/organizations/{org['id']}", headers=viewer["headers"])).status_code == 200
    r = await client.post(f"/api/v1/organizations/{org['id']}/members", headers=viewer["headers"],
                          json={"email": unique_email(), "role_key": "member"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"
    r = await client.patch(f"/api/v1/organizations/{org['id']}", headers=viewer["headers"], json={"name": "Hacked"})
    assert r.status_code == 403


async def test_invitation_bound_to_email(client):
    owner = await register(client)
    org = await create_org(client, owner)
    email = unique_email()
    await client.post(f"/api/v1/organizations/{org['id']}/members", headers=owner["headers"],
                      json={"email": email, "role_key": "member"})
    token = latest_event_token("tenant.invitation_created", email)
    intruder = await register(client)
    r = await client.post("/api/v1/invitations/accept", json={"token": token}, headers=intruder["headers"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "invitation_email_mismatch"
    preview = await client.get("/api/v1/invitations/preview", params={"token": token})
    assert preview.status_code == 200 and preview.json()["role_name"] == "Member"


async def test_unverified_user_cannot_invite(client):
    owner = await register(client, verify=False)
    org = await create_org(client, owner)
    r = await client.post(f"/api/v1/organizations/{org['id']}/members", headers=owner["headers"],
                          json={"email": unique_email(), "role_key": "member"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "email_not_verified"


async def test_only_owner_can_grant_owner_and_last_owner_protected(client):
    owner = await register(client)
    org = await create_org(client, owner)
    admin = await _invite_and_accept(client, owner, org["id"], role="admin")
    members = (await client.get(f"/api/v1/organizations/{org['id']}/members", headers=owner["headers"])).json()
    admin_m = next(m for m in members if m["roles"][0]["role_key"] == "admin")
    owner_m = next(m for m in members if m["roles"][0]["role_key"] == "owner")
    # admin cannot promote themselves to owner
    r = await client.put(f"/api/v1/organizations/{org['id']}/members/{admin_m['membership_id']}/roles",
                         headers=admin["headers"], json={"roles": [{"role_key": "owner"}]})
    assert r.status_code == 403
    # admin cannot demote the owner
    r = await client.put(f"/api/v1/organizations/{org['id']}/members/{owner_m['membership_id']}/roles",
                         headers=admin["headers"], json={"roles": [{"role_key": "viewer"}]})
    assert r.status_code == 403
    # the only owner cannot demote or remove themselves
    r = await client.put(f"/api/v1/organizations/{org['id']}/members/{owner_m['membership_id']}/roles",
                         headers=owner["headers"], json={"roles": [{"role_key": "admin"}]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_owner"
    r = await client.delete(f"/api/v1/organizations/{org['id']}/members/{owner_m['membership_id']}",
                            headers=owner["headers"])
    assert r.status_code == 409
    # owner promotes admin, then can step down
    r = await client.put(f"/api/v1/organizations/{org['id']}/members/{admin_m['membership_id']}/roles",
                         headers=owner["headers"], json={"roles": [{"role_key": "owner"}]})
    assert r.status_code == 200
    r = await client.put(f"/api/v1/organizations/{org['id']}/members/{owner_m['membership_id']}/roles",
                         headers=owner["headers"], json={"roles": [{"role_key": "admin"}]})
    assert r.status_code == 200


async def test_agency_clients(client):
    agency_owner = await register(client)
    agency = await create_org(client, agency_owner, "Pixel Agency", "agency")
    r = await client.post(f"/api/v1/organizations/{agency['id']}/clients", headers=agency_owner["headers"],
                          json={"name": "Green Realty"})
    assert r.status_code == 201, r.text
    client_org = r.json()
    assert client_org["tenant_type"] == "client" and client_org["parent_tenant_id"] == agency["id"]
    # agency owner can operate inside the client via agency access
    got = await client.get(f"/api/v1/organizations/{client_org['id']}", headers=agency_owner["headers"])
    assert got.status_code == 200 and got.json()["access"] == "agency"
    assert "agency.clients.create" not in got.json()["permissions"]
    ws = await client.post(f"/api/v1/organizations/{client_org['id']}/workspaces", headers=agency_owner["headers"],
                           json={"name": "Spring Launch"})
    assert ws.status_code == 201
    orgs = (await client.get("/api/v1/organizations", headers=agency_owner["headers"])).json()
    assert {o["access"] for o in orgs} == {"member", "agency"}
    # audit records agency access
    audit = owner_query("SELECT metadata->>'via' FROM audit_logs WHERE action = 'workspace.created'")
    assert audit == [("agency",)]

    # an agency 'sales' member (no agency.clients.access) cannot reach the client
    sales = await _invite_and_accept(client, agency_owner, agency["id"], role="sales")
    r = await client.get(f"/api/v1/organizations/{client_org['id']}", headers=sales["headers"])
    assert r.status_code == 404
    assert client_org["id"] not in {o["id"] for o in (await client.get(
        "/api/v1/organizations", headers=sales["headers"])).json()}

    # a business org cannot create clients
    biz_owner = await register(client)
    biz = await create_org(client, biz_owner)
    r = await client.post(f"/api/v1/organizations/{biz['id']}/clients", headers=biz_owner["headers"],
                          json={"name": "Nope"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_an_agency"


async def test_custom_role_cannot_escalate(client):
    owner = await register(client)
    org = await create_org(client, owner)
    r = await client.post(f"/api/v1/organizations/{org['id']}/roles", headers=owner["headers"],
                          json={"key": "content_lead", "name": "Content lead",
                                "permissions": ["brands.read", "brands.manage", "creatives.generate"]})
    assert r.status_code == 201, r.text
    manager = await _invite_and_accept(client, owner, org["id"], role="admin")
    # admin lacks organization.delete -> cannot mint a role holding it
    r = await client.post(f"/api/v1/organizations/{org['id']}/roles", headers=manager["headers"],
                          json={"key": "superrole", "name": "Super", "permissions": ["organization.delete"]})
    assert r.status_code == 403
    roles = (await client.get(f"/api/v1/organizations/{org['id']}/roles", headers=owner["headers"])).json()
    assert "content_lead" in {r["key"] for r in roles} and "owner" in {r["key"] for r in roles}
    # system role keys are reserved
    r = await client.post(f"/api/v1/organizations/{org['id']}/roles", headers=owner["headers"],
                          json={"key": "owner", "name": "Fake owner", "permissions": ["brands.read"]})
    assert r.status_code == 409

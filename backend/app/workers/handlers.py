"""Outbox event handlers. Each handler must be idempotent: it may run more than once for the same event."""

from __future__ import annotations

from app.shared.notifications import Email, send_email
from app.shared.outbox import OutboxEvent, handles
from app.shared.storage import get_storage, tenant_prefix


@handles("identity.email_verification_requested")
async def send_verification_email(event: OutboxEvent) -> None:
    p = event.payload
    await send_email(Email(
        to=p["email"], subject="Verify your XploAds email address",
        text=(f"Hi {p['full_name']},\n\nConfirm your email address to finish setting up XploAds:\n\n{p['link']}\n\n"
              "This link expires in 48 hours. If you did not create an account, ignore this email."),
    ))


@handles("identity.password_reset_requested")
async def send_password_reset_email(event: OutboxEvent) -> None:
    p = event.payload
    await send_email(Email(
        to=p["email"], subject="Reset your XploAds password",
        text=(f"Hi {p['full_name']},\n\nUse this link to choose a new password:\n\n{p['link']}\n\n"
              "It expires in 30 minutes. If you did not ask for this, you can ignore this email."),
    ))


@handles("tenant.invitation_created")
async def send_invitation_email(event: OutboxEvent) -> None:
    p = event.payload
    await send_email(Email(
        to=p["email"], subject=f"{p['inviter_name']} invited you to {p['organization_name']} on XploAds",
        text=(f"{p['inviter_name']} invited you to join {p['organization_name']} as {p['role_name']}.\n\n"
              f"Accept the invitation:\n\n{p['link']}\n\nThis invitation expires in 7 days."),
    ))


@handles("storage.object_delete_requested")
async def delete_stored_object(event: OutboxEvent) -> None:
    """Remove an asset's object after its row was deleted or rejected. Deleting a missing object is a no-op."""
    key = event.payload["key"]
    # Defence in depth: only ever delete inside the emitting tenant's prefix.
    if not event.tenant_id or not key.startswith(tenant_prefix(event.tenant_id)):
        raise ValueError("refusing to delete an object outside the event tenant's prefix")
    await get_storage().delete(key)

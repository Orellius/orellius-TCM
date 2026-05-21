"""Audit logging service — records all state-changing operations.

Usage:
    await audit_log(
        action="approve",
        resource_type="message",
        resource_id="msg-123",
        user_id=1,
        org_id=1,
        ip_address="127.0.0.1",
        metadata={"edited": True},
    )
"""

import logging
from datetime import datetime

from sqlalchemy import select

from app.db.models import AuditLog
from app.db.session import async_session

logger = logging.getLogger(__name__)


async def audit_log(
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    user_id: int | None = None,
    org_id: int | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Record an audit log entry."""
    try:
        async with async_session() as session:
            entry = AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                org_id=org_id,
                ip_address=ip_address,
                metadata_=metadata or {},
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        # Never let audit logging break the main flow
        logger.error(f"Failed to write audit log: {e}")


async def query_audit_logs(
    org_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Query audit logs with filters."""
    async with async_session() as session:
        query = select(AuditLog).order_by(AuditLog.timestamp.desc())

        if org_id is not None:
            query = query.where(AuditLog.org_id == org_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if from_date:
            query = query.where(AuditLog.timestamp >= from_date)
        if to_date:
            query = query.where(AuditLog.timestamp <= to_date)

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "user_id": row.user_id,
                "org_id": row.org_id,
                "metadata": row.metadata_,
                "ip_address": row.ip_address,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            for row in rows
        ]


async def export_audit_csv(org_id: int, limit: int = 10000) -> str:
    """Export audit logs as CSV string."""
    import csv
    import io

    logs = await query_audit_logs(org_id=org_id, limit=limit)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "action", "resource_type", "resource_id", "user_id", "metadata", "ip_address", "timestamp"],
    )
    writer.writeheader()
    for log in logs:
        writer.writerow(log)

    return output.getvalue()

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import or_, select

from app.db.models import Reminder
from app.db.session import SessionLocal


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return _ensure_timezone(datetime.fromisoformat(normalized))


def create_reminder(session_id: str, title: str, remind_at: datetime) -> Reminder:
    with SessionLocal() as db:
        reminder = Reminder(
            session_id=session_id,
            title=title.strip(),
            remind_at=_ensure_timezone(remind_at),
            status="pending",
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder


def list_reminders(session_id: str, include_completed: bool = False) -> list[Reminder]:
    with SessionLocal() as db:
        statement = select(Reminder).where(Reminder.session_id == session_id)
        if not include_completed:
            statement = statement.where(Reminder.status == "pending")
        statement = statement.order_by(Reminder.remind_at.asc())
        return list(db.scalars(statement).all())


def cancel_reminder(reminder_id: str) -> Optional[Reminder]:
    with SessionLocal() as db:
        reminder = db.get(Reminder, reminder_id)
        if reminder is None:
            return None
        reminder.status = "cancelled"
        db.commit()
        db.refresh(reminder)
        return reminder


def cancel_reminder_for_session(session_id: str, title_or_id: str) -> Optional[Reminder]:
    needle = title_or_id.strip()
    with SessionLocal() as db:
        statement = (
            select(Reminder)
            .where(Reminder.session_id == session_id)
            .where(Reminder.status == "pending")
            .where(or_(Reminder.id == needle, Reminder.title.ilike(f"%{needle}%")))
            .order_by(Reminder.remind_at.asc())
        )
        reminder = db.scalars(statement).first()
        if reminder is None:
            return None
        reminder.status = "cancelled"
        db.commit()
        db.refresh(reminder)
        return reminder


def get_due_reminders() -> list[Reminder]:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        statement = (
            select(Reminder)
            .where(Reminder.status == "pending")
            .where(Reminder.remind_at <= now)
            .order_by(Reminder.remind_at.asc())
        )
        return list(db.scalars(statement).all())


def serialize_reminder(reminder: Reminder) -> dict[str, str]:
    return {
        "id": reminder.id,
        "session_id": reminder.session_id,
        "title": reminder.title,
        "remind_at": _ensure_timezone(reminder.remind_at).isoformat(),
        "status": reminder.status,
        "created_at": _ensure_timezone(reminder.created_at).isoformat(),
    }


def serialize_reminders(reminders: Iterable[Reminder]) -> list[dict[str, str]]:
    return [serialize_reminder(reminder) for reminder in reminders]

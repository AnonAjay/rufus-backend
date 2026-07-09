from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


# TODO(db-models): Feature branches that add persistent memory, device state,
# audit logs, reminders, and integration state should import their models here
# so Alembic can discover them.

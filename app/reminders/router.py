from fastapi import APIRouter, Query

from app.reminders.service import list_reminders, serialize_reminders


router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("")
async def get_reminders(
    session_id: str = Query(..., min_length=1),
    include_completed: bool = False,
) -> dict[str, list[dict[str, str]]]:
    reminders = list_reminders(session_id, include_completed=include_completed)
    return {"reminders": serialize_reminders(reminders)}

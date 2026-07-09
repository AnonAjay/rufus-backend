from fastapi import APIRouter, HTTPException, status

from app.stunts.library import STUNT_LIBRARY


router = APIRouter(prefix="/stunts", tags=["stunts"])


@router.get("")
async def list_stunts() -> dict[str, list[str]]:
    return {"stunts": sorted(STUNT_LIBRARY)}


@router.get("/{name}")
async def get_stunt(name: str) -> dict[str, object]:
    stunt = STUNT_LIBRARY.get(name)
    if stunt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown stunt")
    return {"name": name, "sequence": stunt}

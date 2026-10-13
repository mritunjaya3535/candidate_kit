from fastapi import APIRouter, HTTPException
from app.src.config.database import client

router = APIRouter()


@router.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

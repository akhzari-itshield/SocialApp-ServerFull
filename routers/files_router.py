from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from auth import get_current_user
from database import get_db
from config import settings
import os, uuid, aiofiles
import models

router = APIRouter(prefix="/files", tags=["files"])
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    chat_id: int | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1]
    fname = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, fname)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    size = 0
    async with aiofiles.open(path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                await f.close()
                os.remove(path)
                raise HTTPException(413, "File too large")
            await f.write(chunk)
    record = models.FileRecord(
        uploader_id=user.id, stored_name=fname, original_name=file.filename,
        mime_type=file.content_type, size_bytes=size, chat_id=chat_id,
    )
    db.add(record); db.commit(); db.refresh(record)
    return {"id": record.id, "url": f"/files/{fname}",
            "size": size, "name": file.filename}


@router.get("/{fname}")
def get_file(fname: str):
    path = os.path.join(settings.UPLOAD_DIR, fname)
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path)

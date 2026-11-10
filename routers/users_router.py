from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from ws_manager import manager
import models, schemas
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from config import settings
from ws_manager import manager
import models, schemas
import os, uuid, aiofiles
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.put("/me", response_model=schemas.UserOut)
def update_me(
    data: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if data.display_name is not None:
        user.display_name = data.display_name.strip() or None
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url.strip() or None
    db.commit()
    db.refresh(user)
    return user


@router.get("/search")
def search_users(q: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    users = (
        db.query(models.User)
        .filter(
            (models.User.phone_number.contains(q)) |
            (models.User.display_name.contains(q))
        )
        .limit(20)
        .all()
    )
    return [
        {
            "id": u.id,
            "phone_number": u.phone_number,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "is_online": manager.is_online(u.id),
        }
        for u in users
    ]


@router.get("/{uid}")
def get_user_by_id(uid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    return {
        "id": u.id,
        "phone_number": u.phone_number,
        "display_name": u.display_name,
        "avatar_url": u.avatar_url,
        "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        "is_online": manager.is_online(u.id),
    }
@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "فقط فایل تصویری مجاز است")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, fname)

    max_bytes = 5 * 1024 * 1024  # 5 MB
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
                raise HTTPException(413, "حجم تصویر بیش از ۵ مگابایت است")
            await f.write(chunk)


    if user.avatar_url:
        old_name = user.avatar_url.split("/")[-1]
        old_path = os.path.join(settings.UPLOAD_DIR, old_name)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    user.avatar_url = f"/files/{fname}"
    db.commit()
    return {"avatar_url": user.avatar_url}

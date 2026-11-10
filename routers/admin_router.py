from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from typing import Optional, List
import os
import uuid
import aiofiles

from database import get_db
from config import settings
import models, schemas, auth

router = APIRouter(prefix="/admin", tags=["admin"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_current_admin(token: str = Depends(auth.security)):
    try:
        payload = jwt.decode(token.credentials, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid admin token")
    if payload.get("type") != "admin":
        raise HTTPException(401, "Not an admin")
    return payload.get("sub")


# ---------- Auth ----------
@router.post("/login")
def admin_login(data: schemas.AdminLogin, db: Session = Depends(get_db)):
    a = db.query(models.AdminUser).filter(models.AdminUser.username == data.username).first()
    if not a or not pwd.verify(data.password, a.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode({
        "sub": a.username, "type": "admin",
        "exp": datetime.utcnow() + timedelta(hours=12),
    }, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"access_token": token}


# ---------- Stats ----------
@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    total_size = db.query(func.sum(models.FileRecord.size_bytes)).scalar() or 0
    return {
        "total_users": db.query(models.User).count(),
        "active_users": db.query(models.User).filter(models.User.is_active == True).count(),
        "inactive_users": db.query(models.User).filter(models.User.is_active == False).count(),
        "new_users_today": db.query(models.User).filter(models.User.created_at >= day_ago).count(),
        "new_users_week": db.query(models.User).filter(models.User.created_at >= week_ago).count(),
        "total_chats": db.query(models.Chat).count(),
        "private_chats": db.query(models.Chat).filter(models.Chat.type == "private").count(),
        "groups": db.query(models.Chat).filter(models.Chat.type == "group").count(),
        "channels": db.query(models.Chat).filter(models.Chat.type == "channel").count(),
        "total_messages": db.query(models.Message).count(),
        "active_messages": db.query(models.Message).filter(models.Message.is_deleted == False).count(),
        "total_files": db.query(models.FileRecord).count(),
        "total_file_size": total_size,
        "total_calls": db.query(models.CallSession).count(),
    }


# ---------- Users ----------
@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(models.User).order_by(models.User.id.desc()).all()


@router.get("/users/{uid}", response_model=schemas.UserOut)
def get_user(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    return u


@router.put("/users/{uid}")
def update_user(uid: int, data: schemas.UserUpdate,
                db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    if data.is_active is not None:
        u.is_active = data.is_active
    if data.display_name is not None:
        u.display_name = data.display_name
    if data.permissions is not None:
        u.permissions = data.permissions
    db.commit()
    return {"ok": True}


@router.post("/users/{uid}/toggle")
def toggle_user(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    u.is_active = not u.is_active
    db.commit()
    return {"is_active": u.is_active}


@router.delete("/users/{uid}")
def delete_user(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404, "User not found")

    for f in db.query(models.FileRecord).filter(models.FileRecord.uploader_id == uid).all():
        path = os.path.join(settings.UPLOAD_DIR, f.stored_name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        db.delete(f)
    db.flush()

    db.query(models.CallSession).filter(
        (models.CallSession.caller_id == uid) |
        (models.CallSession.callee_id == uid)
    ).delete(synchronize_session=False)
    db.flush()

    db.query(models.Chat).filter(models.Chat.created_by == uid).update(
        {models.Chat.created_by: None}, synchronize_session=False
    )
    db.flush()

    db.delete(u)
    db.commit()
    return {"ok": True}


@router.post("/users/{uid}/generate-otp")
def gen_otp(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    otp = auth.generate_otp()
    u.otp_code = otp
    u.otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    db.commit()
    return {"otp": otp, "expires_at": u.otp_expires_at.isoformat()}


@router.get("/users/{uid}/otp")
def view_otp(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u or not u.otp_code:
        raise HTTPException(404, "No active OTP")
    return {"otp": u.otp_code, "expires_at": u.otp_expires_at.isoformat()}


@router.get("/users/{uid}/chats")
def user_chats(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    u = db.query(models.User).get(uid)
    if not u:
        raise HTTPException(404)
    return [
        {"chat_id": m.chat.id, "type": m.chat.type,
         "title": m.chat.title, "role": m.role,
         "member_count": len(m.chat.memberships)}
        for m in u.memberships
    ]


@router.get("/users/{uid}/files")
def user_files(uid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    files = db.query(models.FileRecord).filter(
        models.FileRecord.uploader_id == uid
    ).order_by(models.FileRecord.id.desc()).all()
    return [
        {"id": f.id, "original_name": f.original_name, "size_bytes": f.size_bytes,
         "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in files
    ]


@router.post("/users/{uid}/avatar")
async def admin_upload_avatar(
    uid: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(models.User).get(uid)
    if not user:
        raise HTTPException(404, "User not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "فقط فایل تصویری مجاز است")

    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"avatar_{uid}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    path = os.path.join(settings.UPLOAD_DIR, fname)

    max_bytes = 5 * 1024 * 1024
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
    db.refresh(user)
    return {"avatar_url": user.avatar_url}


# ---------- Chats / Groups / Channels ----------
def _chat_summary(c: models.Chat) -> dict:
    return {
        "id": c.id, "type": c.type, "title": c.title,
        "description": c.description,
        "created_by": c.created_by,
        "member_count": len(c.memberships),
        "admin_count": sum(1 for m in c.memberships if m.role in ("admin", "owner")),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/chats")
def list_chats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chats = db.query(models.Chat).order_by(models.Chat.id.desc()).all()
    return [_chat_summary(c) for c in chats]


@router.get("/groups")
def list_groups(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    groups = db.query(models.Chat).filter(models.Chat.type == "group")\
        .order_by(models.Chat.id.desc()).all()
    return [_chat_summary(c) for c in groups]


@router.get("/channels")
def list_channels(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chans = db.query(models.Chat).filter(models.Chat.type == "channel")\
        .order_by(models.Chat.id.desc()).all()
    return [_chat_summary(c) for c in chans]


@router.get("/private-chats")
def list_private_chats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chats = (
        db.query(models.Chat)
        .filter(models.Chat.type == "private")
        .order_by(models.Chat.id.desc())
        .all()
    )
    result = []
    for c in chats:
        users = []
        for m in c.memberships:
            u = m.user
            if u:
                users.append({
                    "id": u.id,
                    "phone": u.phone_number,
                    "name": u.display_name,
                })
        msg_count = db.query(models.Message).filter(
            models.Message.chat_id == c.id
        ).count()
        result.append({
            "id": c.id,
            "type": "private",
            "users": users,
            "message_count": msg_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@router.get("/chats/{cid}")
def chat_detail(cid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404)
    msgs = db.query(models.Message).filter(models.Message.chat_id == cid)\
        .order_by(models.Message.id.desc()).limit(2000).all()
    return {
        **_chat_summary(chat),
        "members": [
            {"user_id": m.user_id,
             "phone_number": m.user.phone_number,
             "display_name": m.user.display_name,
             "role": m.role,
             "joined_at": m.joined_at.isoformat() if m.joined_at else None}
            for m in chat.memberships
        ],
        "messages": [
            {"id": m.id, "sender_id": m.sender_id, "content": m.content,
             "message_type": m.message_type, "file_url": m.file_url,
             "is_deleted": m.is_deleted,
             "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in reversed(msgs)
        ],
    }


@router.get("/chats/{cid}/messages")
def admin_chat_messages(cid: int, limit: int = 500, before_id: int | None = None,
                        db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404)
    q = db.query(models.Message).filter(models.Message.chat_id == cid)
    if before_id:
        q = q.filter(models.Message.id < before_id)
    msgs = q.order_by(models.Message.id.desc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_phone": m.sender.phone_number if m.sender else None,
            "sender_name": m.sender.display_name if m.sender else None,
            "content": m.content,
            "message_type": m.message_type,
            "file_url": m.file_url,
            "is_deleted": m.is_deleted,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in reversed(msgs)
    ]


@router.post("/chats/{cid}/members/{uid}/role")
def set_role(cid: int, uid: int, role: str,
             db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if role not in ("owner", "admin", "member"):
        raise HTTPException(400, "Invalid role")
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404)
    for m in chat.memberships:
        if m.user_id == uid:
            m.role = role
            db.commit()
            return {"ok": True}
    raise HTTPException(404, "Member not found")


@router.delete("/chats/{cid}/members/{uid}")
def kick_member(cid: int, uid: int,
                db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404)
    for m in list(chat.memberships):
        if m.user_id == uid:
            db.delete(m)
            db.commit()
            return {"ok": True}
    raise HTTPException(404, "Member not found")


@router.post("/chats/{cid}/members/{uid}")
def admin_add_member(cid: int, uid: int,
                     db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404, "Chat not found")
    if chat.type == "private":
        raise HTTPException(400, "Cannot add to private chat")
    user = db.query(models.User).get(uid)
    if not user:
        raise HTTPException(404, "User not found")
    if chat.is_member(uid):
        return {"ok": True, "already_member": True, "user_id": uid}
    chat.memberships.append(models.ChatMember(user_id=uid, role="member"))
    db.commit()
    return {"ok": True, "already_member": False, "user_id": uid}


@router.post("/chats/{cid}/members-by-phone")
def admin_add_member_by_phone(cid: int, phone: str,
                              db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404, "Chat not found")
    if chat.type == "private":
        raise HTTPException(400, "Cannot add to private chat")
    user = db.query(models.User).filter(models.User.phone_number == phone).first()
    if not user:
        raise HTTPException(404, f"User with phone {phone} not found")
    if chat.is_member(user.id):
        return {"ok": True, "already_member": True, "user_id": user.id,
                "display_name": user.display_name}
    chat.memberships.append(models.ChatMember(user_id=user.id, role="member"))
    db.commit()
    return {"ok": True, "already_member": False, "user_id": user.id,
            "display_name": user.display_name}


@router.delete("/chats/{cid}")
def delete_chat(cid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    chat = db.query(models.Chat).get(cid)
    if not chat:
        raise HTTPException(404)
    db.delete(chat)
    db.commit()
    return {"ok": True}


# ---------- Files ----------
@router.get("/files")
def list_files(q: str = "", db: Session = Depends(get_db), _=Depends(get_current_admin)):
    query = db.query(models.FileRecord)
    if q:
        query = query.filter(models.FileRecord.original_name.contains(q))
    files = query.order_by(models.FileRecord.id.desc()).limit(500).all()
    return [
        {"id": f.id, "original_name": f.original_name,
         "mime_type": f.mime_type, "size_bytes": f.size_bytes,
         "uploader_id": f.uploader_id,
         "uploader_phone": f.uploader.phone_number if f.uploader else None,
         "chat_id": f.chat_id, "url": f"/files/{f.stored_name}",
         "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in files
    ]


@router.delete("/files/{fid}")
def delete_file(fid: int, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    f = db.query(models.FileRecord).get(fid)
    if not f:
        raise HTTPException(404)
    path = os.path.join(settings.UPLOAD_DIR, f.stored_name)
    if os.path.exists(path):
        os.remove(path)
    db.delete(f)
    db.commit()
    return {"ok": True}


# ---------- Messages search ----------
@router.get("/messages/search")
def search_messages(q: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if len(q) < 2:
        raise HTTPException(400, "Query too short")
    msgs = db.query(models.Message).filter(
        models.Message.content.contains(q),
    ).order_by(models.Message.id.desc()).limit(200).all()
    return [
        {"id": m.id, "chat_id": m.chat_id, "sender_id": m.sender_id,
         "content": m.content, "message_type": m.message_type,
         "is_deleted": m.is_deleted,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in msgs
    ]


# ---------- Calls ----------
@router.get("/calls")
def list_calls(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    calls = db.query(models.CallSession).order_by(models.CallSession.id.desc())\
        .limit(200).all()
    return [
        {"id": c.id, "caller_id": c.caller_id, "callee_id": c.callee_id,
         "call_type": c.call_type, "status": c.status,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in calls
    ]


# ---------- Broadcast ----------
@router.post("/broadcast")
async def admin_broadcast(
    content: str,
    user_ids: Optional[List[int]] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    content = (content or "").strip()
    if not content:
        raise HTTPException(400, "متن پیام خالی است")

    system = db.query(models.User).filter(
        models.User.phone_number == "SYSTEM"
    ).first()
    if not system:
        raise HTTPException(500, "کاربر سیستم یافت نشد؛ سرور را ری‌استارت کنید")

    if user_ids:
        targets = db.query(models.User).filter(
            models.User.id.in_(user_ids),
            models.User.is_active == True,
            models.User.phone_number != "SYSTEM",
        ).all()
    else:
        targets = db.query(models.User).filter(
            models.User.is_active == True,
            models.User.phone_number != "SYSTEM",
        ).all()

    if not targets:
        raise HTTPException(404, "هیچ کاربری برای ارسال یافت نشد")

    from ws_manager import manager

    sent_count = 0
    for target in targets:
        chat = None
        for m in system.memberships:
            if m.chat.type == "private":
                member_ids = [x.user_id for x in m.chat.memberships]
                if target.id in member_ids and system.id in member_ids:
                    chat = m.chat
                    break

        if not chat:
            chat = models.Chat(type="private", created_by=system.id)
            db.add(chat)
            db.flush()
            chat.memberships.append(models.ChatMember(user_id=system.id, role="owner"))
            chat.memberships.append(models.ChatMember(user_id=target.id, role="member"))
            db.commit()
            db.refresh(chat)

        msg = models.Message(
            chat_id=chat.id,
            sender_id=system.id,
            content=content,
            message_type="text",
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        await manager.send_to_user(target.id, {
            "event": "new_message",
            "data": {
                "id": msg.id, "chat_id": chat.id, "sender_id": system.id,
                "content": content, "message_type": "text",
                "file_url": None, "reply_to_id": None,
                "created_at": msg.created_at.isoformat(),
            },
        })
        sent_count += 1

    return {
        "sent": sent_count,
        "total_targets": len(targets),
        "message": f"پیام به {sent_count} کاربر ارسال شد",
    }

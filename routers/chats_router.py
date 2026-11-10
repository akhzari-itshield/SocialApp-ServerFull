from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from auth import get_current_user
from ws_manager import manager
import models, schemas

router = APIRouter(prefix="/chats", tags=["chats"])


def _to_out(c: models.Chat) -> dict:
    return {
        "id": c.id,
        "type": c.type,
        "title": c.title,
        "member_ids": [m.user_id for m in c.memberships],
    }


def _member_to_dict(m: models.ChatMember) -> dict:
    u = m.user
    return {
        "id": u.id,
        "phone_number": u.phone_number,
        "display_name": u.display_name,
        "avatar_url": u.avatar_url,
        "role": m.role,
        "last_read_message_id": m.last_read_message_id,
        "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        "is_online": manager.is_online(u.id),
    }


@router.post("/", response_model=schemas.ChatOut)
def create_chat(data: schemas.ChatCreate, db: Session = Depends(get_db),
                user=Depends(get_current_user)):
    if data.type not in ("private", "group", "channel"):
        raise HTTPException(400, "Invalid chat type")


    if data.type == "group":
        if user.permissions.get("create_group") is False:
            raise HTTPException(403, "ساخت گروه توسط مدیر غیرفعال شده")
    if data.type == "channel":
        if user.permissions.get("create_channel") is False:
            raise HTTPException(403, "ساخت کانال توسط مدیر غیرفعال شده")

    if data.type == "private":
        if len(data.member_ids) != 1:
            raise HTTPException(400, "Private chat needs exactly one other member")
        other = db.query(models.User).get(data.member_ids[0])
        if not other:
            raise HTTPException(404, "Other user not found")
        for c in user.chats:
            if c.type == "private" and len(c.memberships) == 2:
                if any(m.user_id == other.id for m in c.memberships):
                    return _to_out(c)

    chat = models.Chat(type=data.type, title=data.title, created_by=user.id)
    db.add(chat)
    db.flush()

    chat.memberships.append(models.ChatMember(user_id=user.id, role="owner"))


    for uid in data.member_ids:
        m_user = db.query(models.User).get(uid)
        if m_user and not chat.is_member(uid):
            chat.memberships.append(models.ChatMember(user_id=uid, role="member"))

    db.commit()
    db.refresh(chat)
    return _to_out(chat)


@router.get("/", response_model=list[schemas.ChatOut])
def list_chats(user=Depends(get_current_user)):
    return [_to_out(c) for c in user.chats]


@router.get("/{chat_id}/members")
def get_members(chat_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404)
    return [_member_to_dict(m) for m in chat.memberships]


@router.post("/{chat_id}/members/{uid}")
def add_member(chat_id: int, uid: int, db: Session = Depends(get_db),
               user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404)
    if chat.type == "private":
        raise HTTPException(400, "Cannot add to private chat")

    if chat.get_role(user.id) not in ("owner", "admin"):
        raise HTTPException(403, "دسترسی ندارید")
    new = db.query(models.User).get(uid)
    if not new:
        raise HTTPException(404, "User not found")
    if not chat.is_member(uid):
        chat.memberships.append(models.ChatMember(user_id=uid, role="member"))
        db.commit()
    return {"ok": True}


@router.delete("/{chat_id}/members/{uid}")
def remove_member(chat_id: int, uid: int, db: Session = Depends(get_db),
                  user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404)
    if chat.type == "private":
        raise HTTPException(400, "Cannot remove from private chat")
    my_role = chat.get_role(user.id)
    if user.id != uid and my_role not in ("owner", "admin"):
        raise HTTPException(403, "دسترسی ندارید")
    if uid == user.id and my_role == "owner":
        raise HTTPException(400, "مالک نمی‌تواند خارج شود")
    for m in list(chat.memberships):
        if m.user_id == uid:
            db.delete(m)
            db.commit()
            return {"ok": True}
    raise HTTPException(404, "Member not found")


@router.post("/{chat_id}/members/{uid}/role")
def set_member_role(chat_id: int, uid: int, role: str, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    if role not in ("owner", "admin", "member"):
        raise HTTPException(400, "Invalid role")
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404)
    if chat.get_role(user.id) != "owner":
        raise HTTPException(403, "فقط مالک می‌تواند نقش تغییر دهد")
    for m in chat.memberships:
        if m.user_id == uid:
            m.role = role
            db.commit()
            return {"ok": True}
    raise HTTPException(404, "Member not found")


@router.post("/{chat_id}/read")
def mark_read(chat_id: int, message_id: int = Query(...),
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    chat = db.query(models.Chat).get(chat_id)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404)
    for m in chat.memberships:
        if m.user_id == user.id:
            if m.last_read_message_id is None or message_id > m.last_read_message_id:
                m.last_read_message_id = message_id
                db.commit()
            break
    return {"ok": True}

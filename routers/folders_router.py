from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models, schemas

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("/")
def list_folders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    folders = (
        db.query(models.ChatFolder)
        .filter(models.ChatFolder.user_id == user.id)
        .order_by(models.ChatFolder.id)
        .all()
    )
    return [
        {"id": f.id, "name": f.name, "chat_ids": f.chat_ids or []}
        for f in folders
    ]


@router.post("/")
def create_folder(data: schemas.FolderCreate, user=Depends(get_current_user),
                  db: Session = Depends(get_db)):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "نام پوشه خالی است")
    existing = db.query(models.ChatFolder).filter(
        models.ChatFolder.user_id == user.id,
        models.ChatFolder.name == name,
    ).first()
    if existing:
        raise HTTPException(400, "پوشه‌ای با این نام از قبل وجود دارد")
    folder = models.ChatFolder(user_id=user.id, name=name, chat_ids=[])
    db.add(folder); db.commit(); db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "chat_ids": []}


@router.put("/{fid}")
def update_folder(fid: int, data: schemas.FolderUpdate,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    folder = db.query(models.ChatFolder).filter(
        models.ChatFolder.id == fid,
        models.ChatFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(404)
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(400, "نام پوشه خالی است")
    folder.name = name
    db.commit()
    return {"ok": True}


@router.delete("/{fid}")
def delete_folder(fid: int, user=Depends(get_current_user),
                  db: Session = Depends(get_db)):
    folder = db.query(models.ChatFolder).filter(
        models.ChatFolder.id == fid,
        models.ChatFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(404)
    db.delete(folder); db.commit()
    return {"ok": True}


@router.post("/{fid}/chats/{cid}")
def add_chat(fid: int, cid: int, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    folder = db.query(models.ChatFolder).filter(
        models.ChatFolder.id == fid,
        models.ChatFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(404)
    chat = db.query(models.Chat).get(cid)
    if not chat or not chat.is_member(user.id):
        raise HTTPException(404, "چت یافت نشد")
    current = list(folder.chat_ids or [])
    if cid not in current:
        current.append(cid)
    folder.chat_ids = current
    db.commit()
    return {"ok": True, "chat_ids": current}


@router.delete("/{fid}/chats/{cid}")
def remove_chat(fid: int, cid: int, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    folder = db.query(models.ChatFolder).filter(
        models.ChatFolder.id == fid,
        models.ChatFolder.user_id == user.id,
    ).first()
    if not folder:
        raise HTTPException(404)
    current = list(folder.chat_ids or [])
    if cid in current:
        current.remove(cid)
    folder.chat_ids = current
    db.commit()
    return {"ok": True, "chat_ids": current}

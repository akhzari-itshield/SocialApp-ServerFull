# routers/panel_router.py
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import random, string, json

from database import get_db
from config import settings
import models

router = APIRouter(prefix="/panel", tags=["panel"])
templates = Jinja2Templates(directory="templates")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
COOKIE_NAME = "admin_token"


def get_admin(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "admin":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def auth_redirect():
    return RedirectResponse("/panel/login", status_code=302)


def render(template: str, request: Request, active: str, **ctx):
    return templates.TemplateResponse(
        template, {"request": request, "active": active, **ctx}
    )


# ---------- Login ----------
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if get_admin(request):
        return RedirectResponse("/panel/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = db.query(models.AdminUser).filter(models.AdminUser.username == username).first()
    if not admin or not pwd.verify(password, admin.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "نام کاربری یا رمز عبور اشتباه است"},
            status_code=401,
        )
    token = jwt.encode(
        {
            "sub": admin.username,
            "type": "admin",
            "exp": datetime.utcnow() + timedelta(hours=12),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    resp = RedirectResponse("/panel/", status_code=302)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=12 * 3600)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/panel/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ---------- Dashboard ----------
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request)
    if not admin:
        return auth_redirect()
    stats = {
        "total_users": db.query(models.User).count(),
        "active_users": db.query(models.User).filter(models.User.is_active == True).count(),
        "total_chats": db.query(models.Chat).count(),
        "total_messages": db.query(models.Message).count(),
    }
    recent_users = db.query(models.User).order_by(models.User.id.desc()).limit(10).all()
    return render("dashboard.html", request, "dashboard",
                  admin=admin, stats=stats, recent_users=recent_users)


# ---------- Users ----------
@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, q: str = "", db: Session = Depends(get_db)):
    admin = get_admin(request)
    if not admin:
        return auth_redirect()
    query = db.query(models.User)
    if q:
        query = query.filter(
            or_(models.User.phone_number.contains(q),
                models.User.display_name.contains(q))
        )
    users = query.order_by(models.User.id.desc()).all()
    return render("users.html", request, "users", admin=admin, users=users, q=q)


@router.post("/users/{uid}/toggle")
def user_toggle(uid: int, db: Session = Depends(get_db)):
    user = db.query(models.User).get(uid)
    if user:
        user.is_active = not user.is_active
        db.commit()
    return RedirectResponse("/panel/users", status_code=302)


@router.post("/users/{uid}/generate-otp")
def user_generate_otp(uid: int, db: Session = Depends(get_db)):
    user = db.query(models.User).get(uid)
    if user:
        otp = "".join(random.choices(string.digits, k=6))
        user.otp_code = otp
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        db.commit()
    return RedirectResponse(f"/panel/users/{uid}", status_code=302)


@router.get("/users/{uid}", response_class=HTMLResponse)
def user_detail(uid: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request)
    if not admin:
        return auth_redirect()
    user = db.query(models.User).get(uid)
    if not user:
        return RedirectResponse("/panel/users", status_code=302)
    return render("user_detail.html", request, "users", admin=admin, user=user)


@router.post("/users/{uid}")
def user_update(
    uid: int,
    display_name: str = Form(""),
    permissions: str = Form("{}"),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).get(uid)
    if user:
        user.display_name = display_name.strip() or None
        try:
            user.permissions = json.loads(permissions) if permissions.strip() else {}
        except json.JSONDecodeError:
            pass
        db.commit()
    return RedirectResponse(f"/panel/users/{uid}", status_code=302)


# ---------- Chats ----------
@router.get("/chats", response_class=HTMLResponse)
def chats_list(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request)
    if not admin:
        return auth_redirect()
    chats = db.query(models.Chat).order_by(models.Chat.id.desc()).all()
    return render("chats.html", request, "chats", admin=admin, chats=chats)


@router.get("/chats/{cid}", response_class=HTMLResponse)
def chat_detail(cid: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request)
    if not admin:
        return auth_redirect()
    chat = db.query(models.Chat).get(cid)
    if not chat:
        return RedirectResponse("/panel/chats", status_code=302)
    messages = db.query(models.Message).filter(
        models.Message.chat_id == cid
    ).order_by(models.Message.id.desc()).limit(100).all()
    return render("chat_detail.html", request, "chats",
                  admin=admin, chat=chat, messages=messages)

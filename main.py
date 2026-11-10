from routers import folders_router
from fastapi import FastAPI
from database import engine, Base, SessionLocal
from config import settings
from passlib.context import CryptContext
import models

from routers import auth_router, users_router, chats_router, messages_router, \
    files_router, calls_router, ws_router, admin_router, panel_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Social Network API", version="0.1.0")

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(chats_router.router)
app.include_router(messages_router.router)
app.include_router(files_router.router)
app.include_router(calls_router.router)
app.include_router(ws_router.router)
app.include_router(admin_router.router)
app.include_router(panel_router.router)
app.include_router(folders_router.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Social Network"}


def seed_admin():
    db = SessionLocal()
    try:
        if not db.query(models.AdminUser).filter(
            models.AdminUser.username == settings.ADMIN_USERNAME
        ).first():
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            db.add(models.AdminUser(
                username=settings.ADMIN_USERNAME,
                hashed_password=pwd.hash(settings.ADMIN_PASSWORD),
                is_super=True,
            ))
            db.commit()
            print(f"[SEED] Admin '{settings.ADMIN_USERNAME}' created")
    finally:
        db.close()


def seed_system_user():

    db = SessionLocal()
    try:
        sys_user = db.query(models.User).filter(
            models.User.phone_number == "SYSTEM"
        ).first()
        if not sys_user:
            sys_user = models.User(
                phone_number="SYSTEM",
                display_name="مدیریت",
                is_active=False,  
            )
            db.add(sys_user)
            db.commit()
            print(f"[SEED] System user created (id={sys_user.id})")
    finally:
        db.close()


seed_admin()
seed_system_user()

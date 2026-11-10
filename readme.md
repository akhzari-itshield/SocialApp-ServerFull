# 🖥️ SocialApp Server — سرور شبکه اجتماعی

سرور بک‌اند شبکه اجتماعی و پیام‌رسان که با **FastAPI (Python)** توسعه یافته است. این سرور تمام قابلیت‌های یک پیام‌رسان مدرن (چت بلادرنگ، تماس WebRTC، مدیریت گروه/کانال، فایل و رسانه، احراز هویت OTP و...) را برای کلاینت‌های اندروید، وب و دسکتاپ فراهم می‌کند.

##  امکانات
###  احراز هویت و امنیت
- **ثبت‌نام با شماره تلفن** و کد یکبارمصرف (OTP)
- کد OTP توسط مدیر ( دسکتاپ) گرفته می‌شود
- صدور **JWT Token** برای دسترسی‌های بعدی
- جداول جداگانه برای **کاربران** و **ادمین‌ها**
- امکان فعال/غیرفعال کردن کاربران توسط مدیر
- **دسترسی‌های اختصاصی هر کاربر (Feature Flags)** — مدیر می‌تواند قابلیت‌هایی مثل تماس، ارسال فایل یا ساخت گروه را برای هر کاربر جداگانه فعال/غیرفعال کند

###  پیام‌رسانی
- **چت خصوصی** بین دو کاربر
- **گروه** با ظرفیت نامحدود، مدیریت نقش‌ها (مالک / ادمین / عضو)
- **کانال** با محدودیت ارسال پیام فقط برای ادمین‌ها
- ارسال پیام متنی، تصویری، فایلی و صوتی
- **پاسخ / نقل‌قول** به پیام دیگر
- **ویرایش** پیام توسط فرستنده
- **حذف برای همه** (Soft Delete)
- **حذف فقط برای خودم** — پیام از دید یک کاربر پنهان می‌شود ولی دیگران می‌بینند
- **جستجو** در تاریخچه پیام‌های هر چت
- **صفحه‌بندی (Pagination)** 
- **تیک خوانده‌شدن (Read Receipts)**

###  رسانه و فایل
- آپلود فایل تا **۲ گیگابایت** با روش استریم (بدون مصرف حافظه زیاد)
- ذخیره‌سازی **متادیتای فایل** در دیتابیس (`FileRecord`)
- آپلود **آواتار** توسط خود کاربر یا ادمین
- پشتیبانی از انواع فایل: تصویر، ویدیو، سند، صدا و...

###  تماس صوتی و تصویری (WebRTC)
- سیگنالینگ WebRTC از طریق WebSocket
- رویدادهای `call_request`, `call_accept`, `call_reject`, `call_end`
- تبادل Offer/Answer/ICE بین دو کاربر
- پشتیبانی از تماس صوتی و تصویری نقطه‌به‌نقطه (P2P)

###  وضعیت کاربران
- تشخیص **آنلاین/آفلاین** با استفاده از WebSocket
- ذخیره‌ی **آخرین بازدید** (`last_seen`) هنگام قطع اتصال
- ارسال رویداد `user_online` / `user_offline` به کاربران دیگر

###  سازماندهی
- **پوشه‌بندی چت‌ها (Folders)** — هر کاربر می‌تواند چت‌هایش را در پوشه‌های مجزا سازمان‌دهی کند

###  مدیریت و نظارت
- **پیام همگانی** از طرف کاربر «SYSTEM» به همه یا گروهی از کاربران
- **مشاهده‌ی تمام چت‌ها** (خصوصی، گروه، کانال) از پنل مدیریت
- **افزودن/حذف عضو** از گروه یا کانال توسط ادمین
- **تغییر نقش اعضا** (مالک / ادمین / عضو)
- آمار کامل سیستم (کاربران، چت‌ها، پیام‌ها، فایل‌ها، تماس‌ها)

###  پنل‌های مدیریت
- **پنل وب** با `Jinja2 + Bootstrap RTL` روی مسیر `/panel` 
- **پنل دسکتاپ** با `PySide6` (پروژه‌ی جداگانه)
- هر دو پنل از طریق **REST API** با سرور در ارتباط هستند


## تکنولوژی‌ها

| بخش | تکنولوژی |
|---|---|
| **زبان** | Python 3.10+ |
| **فریمورک وب** | FastAPI |
| **سرور ASGI** | Uvicorn |
| **دیتابیس** | SQLite (پیش‌فرض) / PostgreSQL (توصیه‌شده برای production) |
| **ORM** | SQLAlchemy 2.x |
| **اعتبارسنجی** | Pydantic v2 |
| **احراز هویت** | JWT (python-jose) |
| **هش پسورد** | bcrypt |
| **WebSocket** | WebSocket پروتکل بومی FastAPI |
| **آپلود فایل** | aiofiles (استریم غیرمسدودکننده) |
| **قالب‌بندی پنل وب** | Jinja2 |
| **سیگنالینگ WebRTC** | از طریق WebSocket |


## ساختار پروژه
```
social_server/
├── main.py 
├── config.py #  (SECRET_KEY, DATABASE_URL, ...)
├── database.py #  SQLAlchemy
├── models.py # مدل‌های دیتابیس
├── schemas.py # Pydantic schemas
├── auth.py #  JWT و OTP
├── ws_manager.py #  WebSocket 
├── requirements.txt
├── uploads/ # پوشه‌ی ذخیره‌ی فایل‌ها و آواتارها
├── social_app.db # دیتابیس SQLite 
│
├── routers/
│ ├── init.py
│ ├── auth_router.py # /auth/*
│ ├── users_router.py # /users/*
│ ├── chats_router.py # /chats/*
│ ├── messages_router.py # /messages/*
│ ├── files_router.py # /files/*
│ ├── calls_router.py # /calls/*
│ ├── folders_router.py # /folders/*
│ ├── ws_router.py # /ws (WebSocket)
│ ├── admin_router.py # /admin/*
│ └── panel_router.py # /panel/* (پنل وب)
│
└── templates/ #  HTML پنل وب
├── base.html
├── login.html
├── dashboard.html
├── users.html
├── user_detail.html
├── chats.html
└── chat_detail.html
```

---

##  راه‌اندازی
### گام ۱: کلون کردن پروژه

```
git clone https://github.com/akhzari-itshield/SocialApp-Server.git
cd SocialApp-Server
```
### گام ۲:نصب وابستگی‌ها
```
pip install -r requirements.txt
```
### گام ۳: تنظیم config.py
```
class Settings(BaseSettings):

    SECRET_KEY: str = "YOUR_RANDOM_LONG_SECRET_KEY_HERE"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    OTP_EXPIRE_MINUTES: int = 5
    # SQLite (پیش‌فرض)
    DATABASE_URL: str = "sqlite:///./social_app.db"
    # DATABASE_URL: str = "postgresql+psycopg2://user:pass@localhost:5432/social_db"
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 2000
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "ChangeMe_Admin@2025"
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
```
### گام ۴:اجرای سرور 
```
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --ws wsproto
```
### گام ۵: مشاهده‌ی مستندات API

مرورگر خود را باز کنید:

http://localhost:8000/docs — Swagger UI

http://localhost:8000/redoc — ReDoc

### پنل مدیریت وب

پس از اجرای سرور، مرورگر خود را باز کنید:
http://localhost:8000/panel/login
با اطلاعات config.py وارد شوید.

### امکانات پنل وب
داشبورد: آمار کلی + آخرین کاربران
کاربران: لیست، جستجو، فعال/غیرفعال، ساخت OTP، ویرایش
جزئیات کاربر: مشاهده OTP، ویرایش نام و دسترسی‌ها
چت‌ها: لیست همه چت‌ها
جزئیات چت: اعضا و پیام‌های هر چت

### منابع مرتبط

 کلاینت اندروید: SocialApp-Client (Android)
    https://github.com/akhzari-itshield/SocialApp-Client

### ** اگر این پروژه برایتان مفید بود، ستاره بدهید! **

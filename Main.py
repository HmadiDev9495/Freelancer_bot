# =========================
# Imports & Bootstrapping
# =========================
import os
import re
import time
import signal
import atexit
import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List
from urllib.parse import urlparse, parse_qsl
import telebot
from telebot import apihelper
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telebot.apihelper import ApiTelegramException
from mysql.connector import connect, Error
from CONFIG import Config
from Database import FreelanceBot
last_bot_message_id: dict[int, int] = {}
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv
# فرمت لاگ
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler = RotatingFileHandler(
    "logs/bot.log",
    maxBytes=5*1024*1024,
    backupCount=3,
    encoding='utf-8'
)
file_handler.setLevel(Config.loglevel_numeric())
file_handler.setFormatter(formatter)

# هندلر کنسول
console_handler = logging.StreamHandler()
console_handler.setLevel(Config.loglevel_numeric())
console_handler.setFormatter(formatter)

# لاگر اصلی
logger = logging.getLogger("freelance-bot")
logger.setLevel(Config.loglevel_numeric())
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# سکوت کردن لاگ‌های غیرضروری
logging.getLogger("urllib3").setLevel(logging.ERROR)

# --- تنظیمات تلگرام ---
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 60

# --- اپ و بات ---
app: FreelanceBot = FreelanceBot()
bot = telebot.TeleBot(Config.API_TOKEN, parse_mode="HTML")
charset='utf8mb4',
collation='utf8mb4_unicode_ci'

def inline_nav_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_projects"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    return kb

def interactive_exit_handler(_signum=None, _frame=None):
    try:
        ans = input("\nDo you want to purge all user data before exit? (yes/no): ").strip().lower()
    except Exception:
        ans = "no"

    if ans in ("y", "yes"):
        ok = purge_all_data()
        print("[purge] Done." if ok else "[purge] Failed (see logs).")
    else:
        print("No purge.")

    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
@bot.callback_query_handler(func=lambda cq: cq.data == "noop")
def noop_cb(cq):
    # خاموش کردن اسپینر تلگرام
    bot.answer_callback_query(cq.id, text="—")

def show_typing(chat_id, times: int = 1):
    """
    نمایش سریع 'در حال تایپ...' برای UX بهتر.
    times=1 یعنی یک پالس کوتاه. اگر جایی کوئری سنگین داری می‌تونی 2 یا 3 بدی.
    """
    try:
        for _ in range(max(1, int(times))):
            bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

# ==============================================================
# ==== Global "smart send": prefer EDIT over SEND, no code refactor needed ====
from telebot.apihelper import ApiTelegramException

# chat_id -> آخرین message_id ارسالیِ بات در همان چت
_LAST_BOT_MSG: dict[int, int] = {}


if not hasattr(bot, "send_message_orig"):
    bot.send_message_orig = bot.send_message          # type: ignore[attr-defined]
if not hasattr(bot, "edit_message_text_orig"):
    bot.edit_message_text_orig = bot.edit_message_text  # type: ignore[attr-defined]


def _remember_last(chat_id: int, message_id: int):
    _LAST_BOT_MSG[chat_id] = message_id

def _smart_send(chat_id: int, text: str, **kwargs):
    force_new = bool(kwargs.pop("force_new", False))
    mid = _LAST_BOT_MSG.get(chat_id)

    if (not force_new) and mid:
        try:
            msg = bot.edit_message_text_orig(text, chat_id, mid, **kwargs)  # type: ignore[attr-defined]
            _remember_last(chat_id, mid)
            return msg
        except ApiTelegramException:
            pass  # اگر ادیت نشد، می‌افتیم روی ارسال جدید

    msg = bot.send_message_orig(chat_id, text, **kwargs)  # type: ignore[attr-defined]
    try:
        _remember_last(chat_id, msg.message_id)
    except Exception:
        pass
    return msg

def cmd_help(message):
    cid = message.chat.id
    help_text = (
        "🤖 <b>راهنمای کلی</b>\n"
        "• ابتدا ثبت‌نام کنید.\n"
        "• پروفایل خود را کامل کنید.\n"
        "• مهارت‌ها و پروژه‌ها را اضافه کنید.\n"
        "• از داشبورد برای مدیریت استفاده کنید."
    )
    bot.send_message(cid, help_text, parse_mode="HTML", reply_markup=main_menu())

def _smart_edit(text: str, chat_id: int, message_id: int, **kwargs):
    """
    جایگزین edit_message_text تا آخرین پیام بات به‌روز بماند.
    اگر پیام «بدون تغییر» باشد، خطای 400 تلگرام را نادیده می‌گیریم.
    """
    try:
        msg = bot.edit_message_text_orig(text, chat_id, message_id, **kwargs)  # type: ignore[attr-defined]
        try:
            _remember_last(chat_id, message_id)
        except Exception:
            pass
        return msg
    except ApiTelegramException as e:
        # اگر متن/کیبورد دقیقاً همونه: خطا 400 و عبارت 'message is not modified'
        desc = str(getattr(e, "description", "")) or str(e)
        if getattr(e, "error_code", None) == 400 and "message is not modified" in desc.lower():
            # این مورد را نادیده بگیر؛ اجازه بده caller ادامه بده و callback را جواب بده
            return None
        # سایر خطاها را بالا بده تا دیده شوند
        raise


# مونکی‌پچ سراسری
bot.send_message = _smart_send             # type: ignore[assignment]
bot.edit_message_text = _smart_edit        # type: ignore[assignment]

# چند ابزار اختیاری:
def reset_last_message(chat_id: int):
    """اگر جایی نخواستی auto-edit شود، می‌توانی آخرین پیام ذخیره‌شده را پاک کنی."""
    _LAST_BOT_MSG.pop(chat_id, None)

bot.reset_last_message = reset_last_message  # type: ignore[attr-defined]
# ============================================================================
PROJECT_STATUSES = [
    ("all", "همه"),
    ("open", "باز"),
    ("in_progress", "درحال انجام"),
    ("done", "تمام‌شده"),
    ("cancelled", "لغوشده"),
]
# تعداد آیتم‌ها برای نمایش در لیست پروژه‌ها
PROJECT_LIST_LIMIT = 10

# Constants
# =========================
PAGE_SIZE_DEFAULT = 5

CATEGORIES = [
    "توسعه وب", "توسعه نرم‌افزار دسکتاپ", "توسعه موبایل",
    "هوش مصنوعی و یادگیری ماشین", "علوم داده و تحلیل داده", "DevOps و اتوماسیون",
    "امنیت سایبری", "شبکه و زیرساخت", "رایانش ابری",
    "بلاک‌چین و ارزهای دیجیتال", "اینترنت اشیا", "برنامه‌نویسی تعبیه‌شده",
    "توسعه بازی", "طراحی تجربه و رابط کاربری", "تست و تضمین کیفیت",
    "پایگاه‌داده و مدیریت داده‌ها", "مدیریت پروژه نرم‌افزاری",
    "رباتیک و اتوماسیون صنعتی", "واقعیت افزوده و واقعیت مجازی",
    "پشتیبانی فنی و Helpdesk"
]
SKILL_CATEGORIES = PROJECT_CATEGORIES = CATEGORIES
ROLES = ["employer", "freelancer"]
STATUSES = ["draft", "open", "in_progress", "done", "cancelled"]
STATUS_FA = {
    "draft":"پیشنویس", "open":"باز", "in_progress":"در حال انجام",
    "done":"تمام‌شده", "cancelled":"لغوشده"
}

# =========================
# State helpers
# =========================
user_steps:     Dict[int, str]            = {}
user_histories: Dict[int, List[str]]      = {}
user_data:      Dict[int, Dict[str, Any]] = {}
EXPIRING_MESSAGES: Dict[tuple[int, int], float] = {}
EXPIRY_LOCK = threading.Lock()

def send_and_remember(cid, text, **kwargs):
    """پیامی می‌فرستد و id آخرین پیام ارسالی را نگه می‌دارد تا بتوانیم بعداً پاک/ویرایش کنیم."""
    if cid in last_bot_message_id:
        try: bot.delete_message(cid, last_bot_message_id[cid])
        except: pass
    msg = bot.send_message(cid, text, **kwargs)
    last_bot_message_id[cid] = msg.message_id
    return msg

def reset_state(cid: int):
    """پاک‌کردن وضعیت‌ها و داده‌های موقت کاربر."""
    user_steps.pop(cid, None)
    user_histories.pop(cid, None)
    user_data.pop(cid, None)

def push_state(cid: int, state: str):
    """ثبت مرحله‌ی جدید در history و ست‌کردن state جاری."""
    h = user_histories.setdefault(cid, [])
    h.append(state)
    user_steps[cid] = state

def pop_state(cid: int) -> str:
    """بازگشت به مرحله‌ی قبلی (در مسیرهای متنی)."""
    h = user_histories.get(cid, [])
    if h: h.pop()
    if h:
        prev = h.pop()
        user_steps[cid] = prev
        return prev
    return ''

def log_main_event(user, action, chat_id=None):
    """لاگ سبک برای رخدادهای کلیدی (استفاده برای دیباگ)."""
    d = {"user": user, "action": action}
    if chat_id: d["chat_id"] = chat_id
    try: print(d)
    except Exception: pass

# =========================
# Keyboards (Main & Nav)
# =========================
def main_menu() -> InlineKeyboardMarkup:
    """
    منوی اصلی (Inline). بعضی نسخه‌های پراکنده‌ی این تابع در فایل‌ت هست؛
    این نسخه، گزینه‌های خانه/داشبورد/پروفایل/مهارت/پروژه/راهنما رو داره.
    """
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📋 ثبت‌نام", callback_data="menu_register"),
        InlineKeyboardButton("🛠 مهارت‌ها", callback_data="menu_skills"),
        InlineKeyboardButton("📁 پروژه‌ها", callback_data="menu_projects"),
        InlineKeyboardButton("👤 پروفایل من", callback_data="menu_profile"),
        InlineKeyboardButton("❓ راهنما",   callback_data="menu_help"),
        InlineKeyboardButton("📊 داشبورد",  callback_data="menu_dashboard"),
        InlineKeyboardButton("🗂️ پروژه‌ها (فیلتر)", callback_data="view:projects?status=all"),
        )
    # لینک پشتیبانی که قبلاً هم داشتی، اگر می‌خوای نگه‌دار:
    kb.add(InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/Anakin9495"))
    # دکمهٔ بازگشت به خانه (inline) – این، پیام فعلی رو به منوی اصلی برمی‌گردونه
    kb.add(InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_menu"))
    return kb
@bot.message_handler(
    func=lambda m: user_steps.get(m.chat.id) == 'editprofile_wait' and
                   user_data.get(m.chat.id, {}).get("editprofile_field") == "profile_picture",
    content_types=['photo']
)

def profile_edit_picture_handler(m):
    """دریافت عکس از کاربر و ذخیره file_id آن"""
    cid = m.chat.id
    user = app.find_user(cid)
    if not user:
        send_and_remember(cid, "ابتدا وارد شوید.", reply_markup=main_menu())
        reset_state(cid)
        return

    # گرفتن file_id از بالاترین کیفیت عکس
    file_id = m.photo[-1].file_id  # آخرین عنصر = بالاترین رزولوشن

    # ذخیره در دیتابیس
    ok = app.update_user_profile(user['id'], "profile_picture", file_id)
    reset_state(cid)

    if ok:
        send_and_remember(cid, "✅ عکس پروفایل با موفقیت ذخیره شد.", reply_markup=profile_menu_markup())
        # نمایش عکس به کاربر برای تأیید
        bot.send_photo(cid, file_id, caption="عکس پروفایل شما:")
    else:
        send_and_remember(cid, "❌ خطا در ذخیره عکس.", reply_markup=profile_menu_markup())

@bot.message_handler(
    func=lambda m: user_steps.get(m.chat.id) == 'editprofile_wait' and
                   user_data.get(m.chat.id, {}).get("editprofile_field") == "profile_picture",
    content_types=['text']
)
def profile_edit_picture_text_reject(m):
    cid = m.chat.id
    send_and_remember(
        cid,
        "❌ لطفاً یک عکس بفرستید، نه متن.\nبرای انصراف، از دکمه «🔙 بازگشت» استفاده کنید.",
        reply_markup=nav_keyboard()
    )

def _profile_completion_percent(u: dict) -> int:
    important_fields = [
        "name", "email", "role", "bio", "hourly_rate",
        "phone", "linkedin", "github", "website"
    ]
    filled = 0
    for field in important_fields:
        value = u.get(field)
        if value is not None and str(value).strip() != "":
            filled += 1
    return int(round((filled / len(important_fields)) * 100))

def build_summary_text(u: dict | None) -> str:
    if not u:
        return "ابتدا وارد شوید تا خلاصهٔ وضعیت شما نمایش داده شود."
    uid = u.get("id")
    name = (u.get("name") or "کاربر").strip()
    email = u.get("email") or "-"
    role = u.get("role") or "-"
    tg = u.get("telegram_id") or "-"

    total = app.count_projects_by_owner(uid)
    by_open = app.count_projects_by_owner_and_status(uid, "open")
    by_prog = app.count_projects_by_owner_and_status(uid, "in_progress")
    by_done = app.count_projects_by_owner_and_status(uid, "done")

    recent = app.recent_projects(uid, limit=3) or []
    recent_lines = [f"• #{it.get('id')} — {(it.get('title') or 'بدون عنوان').strip()} [{it.get('status','-')}]" for it in recent]

    text = (
        f"🧾 <b>خلاصهٔ وضعیت</b>\n"
        f"نام: <b>{name}</b>\nایمیل: {email}\nنقش: {role}\nTelegram ID: {tg}\n\n"
        f"پروژه‌ها: کل <b>{total}</b>\n"
        f"— باز: {by_open} | درحال انجام: {by_prog} | تمام‌شده: {by_done}\n\n"
        f"آخرین‌ها:\n" + ("\n".join(recent_lines) if recent_lines else "—")
    )
    return text

def show_summary_view(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    u = app.find_user(cid)
    text = build_summary_text(u)
    # کلید تازه‌سازی خودش همین view را دوباره صدا می‌زند
    kb = quick_bar_with_refresh("view:summary")
    bot.edit_message_text(text, cid, cq.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(cq.id, "✅ به‌روز است")


def status_chips_markup(active_key: str = "all"):
    kb = InlineKeyboardMarkup(row_width=4)
    row = []
    for key, label in PROJECT_STATUSES:
        shown = f"● {label}" if key == active_key else label
        row.append(InlineKeyboardButton(shown, callback_data=f"view:projects?status={key}"))
    kb.add(*row)
    return kb

def build_projects_list_text(items: list[dict], active_status: str) -> str:
    title = next((label for key, label in PROJECT_STATUSES if key == active_status), "همه")
    if not items:
        return f"🗂️ پروژه‌ها — {title}\nچیزی پیدا نشد."
    lines = [f"🗂️ پروژه‌ها — {title}"]
    for it in items:
        pid = it.get("id")
        t = (it.get("title") or "بدون عنوان").strip()
        st = it.get("status") or "-"
        lines.append(f"• #{pid} — {t}  [{st}]")
    return "\n".join(lines)


def show_projects_view(cq, status_key: str = "all"):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    status_key = status_key or "all"

    items = app.list_projects_filtered(status=status_key, limit=PROJECT_LIST_LIMIT, offset=0)
    text = build_projects_list_text(items, status_key)

    # سطر چیپ‌های وضعیت + نوار پایین با «تازه‌سازی» همین صفحه
    chips = status_chips_markup(active_key=status_key)
    bottom = quick_bar_with_refresh(f"view:projects?status={status_key}")

    # ترفند ساده: دو مارک‌آپ را در یک کیبورد ادغام کنیم (اول چیپ‌ها، بعد نوار پایین)
    merged = InlineKeyboardMarkup()
    # --- چیپ‌ها
    for row in chips.keyboard:
        merged.row(*row)
    # --- نوار پایین
    for row in bottom.keyboard:
        merged.row(*row)

    bot.edit_message_text(text, cid, cq.message.message_id, reply_markup=merged, parse_mode="HTML")
    bot.answer_callback_query(cq.id)

def quick_bar_with_refresh(current_view_cbdata: str, show_home: bool = True):
    kb = InlineKeyboardMarkup()
    row = [InlineKeyboardButton("🔄 تازه‌سازی", callback_data=current_view_cbdata),
           InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
    if show_home:
        row.append(InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"))
    kb.add(*row)
    return kb

def pager_markup(resource: str, page: int, total_pages: int, extra: str = "", show_home=True):
    """
    resource:  'projects' | 'users' | ...
    page:      شماره صفحه 1-based
    extra:     پارامترهای اضافی در callback (مثلاً فیلترها) مثل 'uid=12'
    """
    kb = InlineKeyboardMarkup(row_width=4)

    def cb(p):
        suffix = f"page={p}"
        if extra:
            suffix += "&" + extra
        return f"p:{resource}:{suffix}"

    left_block = []
    right_block = []
    if page > 1:
        left_block.append(InlineKeyboardButton("⏮️", callback_data=cb(1)))
        left_block.append(InlineKeyboardButton("◀️", callback_data=cb(page - 1)))
    else:
        left_block.append(InlineKeyboardButton("⏮️", callback_data="noop"))
        left_block.append(InlineKeyboardButton("◀️", callback_data="noop"))

    if page < total_pages:
        right_block.append(InlineKeyboardButton("▶️", callback_data=cb(page + 1)))
        right_block.append(InlineKeyboardButton("⏭️", callback_data=cb(total_pages)))
    else:
        right_block.append(InlineKeyboardButton("▶️", callback_data="noop"))
        right_block.append(InlineKeyboardButton("⏭️", callback_data="noop"))

    kb.add(*left_block, InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"), *right_block)

    # ردیف بازگشت/خانه
    row2 = [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")]
    if show_home:
        row2.append(InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"))
    kb.add(*row2)
    return kb

# ===== Lightweight cmd_* shims to avoid "undefined" and make demo work =====
def cmd_register(message):
    """ثبت‌نام سریع: اگر کاربر نبود، می‌سازیم؛ اگر بود، پیام می‌دهیم."""
    cid = message.chat.id
    u = app.find_user(cid)
    if u:
        bot.send_message(cid, "شما قبلاً ثبت‌نام کرده‌اید ✅", reply_markup=main_menu())
        return
    # به خاطر UNIQUE بودن ایمیل، یک ایمیل یکتا بر اساس telegram_id می‌سازیم
    gen_email = f"tg_{cid}@example.local"
    name = (message.from_user.first_name or "کاربر") + ((" " + message.from_user.last_name) if message.from_user.last_name else "")
    # ✅ تولید رمز عبور تصادفی
    import secrets
    temp_password = secrets.token_urlsafe(16)
    uid = app.add_user(telegram_id=cid, name=(name or "کاربر").strip(), email=gen_email, password_hash=temp_password,
                       role="freelancer")
    if uid:
        bot.send_message(cid, "ثبت‌نام سریع انجام شد ✅", reply_markup=main_menu())
        bot.send_message(cid, f"پسورد موقت شما: {temp_password}\nلطفاً آن را تغییر دهید.")
    else:
        bot.send_message(cid, "❌ ثبت‌نام ناموفق بود.", reply_markup=main_menu())

def cmd_projects(message):
    """ورود به منوی پروژه‌ها"""
    cid = message.chat.id
    bot.send_message(cid, "📁 پروژه‌ها:", reply_markup=projects_menu_markup())

def cmd_skills(message):
    """ورود به منوی مهارت‌ها"""
    cid = message.chat.id
    bot.send_message(cid, "🛠 مهارت‌ها:", reply_markup=skills_menu_markup())



# ========================================================================

def nav_keyboard() -> ReplyKeyboardMarkup:
    """
    کیبورد متنی پایین صفحه برای مسیرهای Step-by-step (ثبت‌نام، افزودن مهارت، …)
    قبلاً one_time_keyboard=True بود و بعد از یک بار لمس، ناپدید می‌شد (علت «گم شدن دکمه‌ها»).
    اینجا False شده تا همیشه بماند.
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add("🔙 بازگشت", "🏠 منوی اصلی")
    return kb

def render_projects_page_text(items):
    if not items:
        return "هیچ پروژه‌ای پیدا نشد."
    lines = []
    for it in items:
        pid = it.get("id")
        title = (it.get("title") or "بدون عنوان").strip()
        status = (it.get("status") or "-")
        budget = it.get("budget", None)
        if budget is None:
            lines.append(f"• #{pid} — {title}  [{status}]")
        else:
            lines.append(f"• #{pid} — {title}  [{status}]  💵{budget}")
    return "🗂️ پروژه‌ها:\n" + "\n".join(lines)


# =========================
# Global Back (Inline) — بازگشت به منوی اصلی
# =========================
@bot.callback_query_handler(func=lambda cq: cq.data.startswith("view:"))
def view_router_cb(cq):
    data = cq.data[5:]  # حذف "view:"
    path, _, query = data.partition("?")
    params = dict(parse_qsl(query)) if query else {}

    if path == "summary":
        show_summary_view(cq)
        return

    if path == "projects":
        status_key = params.get("status", "all")
        show_projects_view(cq, status_key=status_key)
        return

    # مسیر ناشناخته
    bot.answer_callback_query(cq.id, text="مسیر نامعتبر")
    return

@bot.callback_query_handler(func=lambda cq: cq.data == "back_to_menu")
def back_to_menu_cb(cq):
    """برگشت inline به خانه (وقتی داخل منوهای inline هستیم)."""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    bot.edit_message_text("🏠 منوی اصلی:", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

# =========================
# Global Back (Reply) — بازگشت در حالت‌های متنی
# =========================
@bot.message_handler(func=lambda m: m.text == "🏠 منوی اصلی")
def reply_home(m):
    """در هر مرحلهٔ متنی اگر کاربر «منوی اصلی» بفرستد، به خانه برگردیم."""
    cid = m.chat.id
    reset_state(cid)
    send_and_remember(cid, "🏠 منوی اصلی:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔙 بازگشت")
def reply_back(m):
    """در مراحل متنی، به مرحله‌ی قبلی برگردیم؛ اگر قبلی نبود، به خانه برویم."""
    cid = m.chat.id
    prev = pop_state(cid)
    if prev:
        send_and_remember(cid, f"↩️ بازگشت به مرحلهٔ قبل: {prev}", reply_markup=nav_keyboard())
    else:
        send_and_remember(cid, "🏠 منوی اصلی:", reply_markup=main_menu())

# =========================
# Navigation: /start + منوی کلی
# =========================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    cid = m.chat.id
    reset_state(cid)
    user = app.find_user(cid)
    if user:
        app.update_user_profile(user['id'], "last_login", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    bot.send_message(
        cid,
        f"سلام {m.from_user.first_name}!\n"
        "برای ادامه یکی از گزینه‌ها را لمس کن:",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("menu_"))

def handle_menu(cq):
    """
    هندلر کلی برای دکمه‌های منوی اصلی:
    menu_register / menu_login / menu_skills / menu_projects / menu_help / menu_dashboard / menu_profile
    """
    cid = cq.message.chat.id
    action = cq.data.split("_", 1)[1]
    log_main_event(cq.from_user.username, action, chat_id=cid)
    # توجه: این توابع (cmd_register, show_login_accounts, cmd_skills, ...) قبلاً در فایل موجودند.
    # الان فقط روتینگ انجام می‌دهیم و دکمهٔ «بازگشت به خانه» هم در منوها هست.
    if   action == "register": globals().get("cmd_register", lambda x: bot.send_message(cid, "تابع cmd_register تعریف نشده است.", reply_markup=main_menu()))(cq.message)
    elif action == "login":    globals().get("show_login_accounts", lambda x: bot.send_message(cid, "تابع show_login_accounts تعریف نشده است.", reply_markup=main_menu()))(cq.message)
    elif action == "skills":   globals().get("cmd_skills", lambda x: bot.send_message(cid, "تابع cmd_skills تعریف نشده است.", reply_markup=main_menu()))(cq.message)
    elif action == "projects": globals().get("cmd_projects", lambda x: bot.send_message(cid, "تابع cmd_projects تعریف نشده است.", reply_markup=main_menu()))(cq.message)
    elif action == "help":
        globals().get("cmd_help", lambda x: bot.send_message(cid, "راهنما در دسترس نیست.", reply_markup=main_menu()))(
            cq.message)
    elif action == "dashboard": dashboard_cb(cq)  # اگر نسخهٔ جدا هم داری، هر دو می‌مانند (حذف نمی‌کنیم)
    elif action == "profile":   globals().get("show_profile", lambda x: bot.send_message(cid, "تابع show_profile تعریف نشده است.", reply_markup=main_menu()))(cq)
    bot.answer_callback_query(cq.id)

def get_contextual_help(current_state: str = None) -> str:
    """بازگرداندن راهنمای متناسب با موقعیت کاربر"""
    if current_state and current_state.startswith("prj_"):
        return (
            "📁 <b>راهنمای پروژه‌ها</b>\n"
            "• «➕ پروژه جدید»: پروژه‌ای با عنوان، توضیح، بودجه و زمان ایجاد کنید.\n"
            "• «📋 لیست پروژه‌ها»: همه پروژه‌های خود را ببینید.\n"
            "• «📂 بر اساس وضعیت»: پروژه‌ها را فیلتر کنید."
        )
    elif current_state and current_state.startswith("skills_"):
        return (
            "🛠 <b>راهنمای مهارت‌ها</b>\n"
            "• «➕ افزودن»: مهارت جدید به پروفایل اضافه کنید.\n"
            "• «📋 لیست من»: مهارت‌های فعلی خود را ببینید.\n"
            "• «✏️ ویرایش/🗑 حذف»: مهارت‌ها را مدیریت کنید."
        )
    elif current_state == "editprofile_wait":
        return (
            "👤 <b>راهنمای ویرایش پروفایل</b>\n"
            "• هر فیلد را به‌صورت جداگانه ویرایش کنید.\n"
            "• برای رمز عبور، حداقل ۶ کاراکتر وارد کنید."
        )
    else:
        return (
            "🤖 <b>راهنمای کلی</b>\n"
            "• ابتدا ثبت‌نام کنید.\n"
            "• پروفایل خود را کامل کنید.\n"
            "• مهارت‌ها و پروژه‌ها را اضافه کنید.\n"
            "• از داشبورد برای مدیریت استفاده کنید."
        )
# =========================
# Skills: منو + افزودن/لیست
# =========================
def skills_menu_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ افزودن", callback_data="skills_add"),
        InlineKeyboardButton("📋 لیست من", callback_data="skills_list"),
        InlineKeyboardButton("✏️ ویرایش", callback_data="skills_edit"),
        InlineKeyboardButton("🗑 حذف", callback_data="skills_delete")
    )

    (kb.add
           (InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_menu"),
           InlineKeyboardButton("❓ راهنما", callback_data="menu_help"),
           ))
    return kb

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_skills")
def menu_skills_cb(cq):
    """نمایش منوی مهارت‌ها (inline)"""
    cancel_message_expiry(cid, last_bot_message_id.get(cid))
    reset_last_message(cid)
    cid = cq.message.chat.id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'skills_menu')
    bot.edit_message_text("مهارت‌ها:", cid, cq.message.message_id, reply_markup=skills_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_add")
def skills_add_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    kb = InlineKeyboardMarkup(row_width=2)
    for idx, cat in enumerate(SKILL_CATEGORIES):
        kb.add(InlineKeyboardButton(cat, callback_data=f"skillcat_{idx}"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="menu_skills"))
    bot.edit_message_text("دسته‌بندی مهارت را انتخاب کنید:", cid, cq.message.message_id, reply_markup=kb)
    schedule_message_expiry(cid, cq.message.message_id, delay_seconds=3600)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("skillcat_"))
def skills_category_selected(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    try:
        idx = int(cq.data.split("_", 1)[1])
        category = SKILL_CATEGORIES[idx]
    except (ValueError, IndexError, IndexError):
        bot.answer_callback_query(cq.id, "دسته‌بندی نامعتبر است.")
        return
    user_data.setdefault(cid, {})["skills_add_category"] = category
    push_state(cid, "skills_add_name")
    bot.edit_message_text("نام مهارت را بفرست:", cid, cq.message.message_id)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "skills_add_name")
def skills_add_name_handler(m):
    cid = m.chat.id
    name = (m.text or "").strip()
    if not name:
        send_and_remember(cid, "❌ نام مهارت نمی‌تواند خالی باشد.", reply_markup=nav_keyboard())
        return
    category = user_data.get(cid, {}).get("skills_add_category")
    if not category:
        send_and_remember(cid, "❌ دسته‌بندی انتخاب نشده است.", reply_markup=main_menu())
        reset_state(cid)
        return

    # === پیش‌نمایش مهارت ===
    preview = f"✅ <b>پیش‌نمایش مهارت</b>\nنام: {name}\nدسته: {category}"
    bot.send_message(cid, preview, parse_mode="HTML")
    time.sleep(1)  # کمی تأخیر برای خوانایی

    # === ثبت نهایی ===
    skill_id = app.add_skill(name, category)
    if not skill_id:
        send_and_remember(cid, "❌ افزودن مهارت با خطا مواجه شد.", reply_markup=skills_menu_markup())
        reset_state(cid)
        return
    user = app.find_user(cid)
    if not user:
        send_and_remember(cid, "❌ کاربر یافت نشد.", reply_markup=main_menu())
        reset_state(cid)
        return
    success = app.add_user_skill(user['id'], skill_id, proficiency=1)
    reset_state(cid)
    if success:
        send_and_remember(cid, f"✅ مهارت «{name}» در دستهٔ «{category}» اضافه و به پروفایل شما متصل شد.", reply_markup=skills_menu_markup())
    else:
        send_and_remember(cid, "❌ اتصال مهارت به پروفایل ناموفق بود.", reply_markup=skills_menu_markup())

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_list")
def skills_list_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    skills = app.list_user_skills(user['id'])
    if not skills:
        bot.edit_message_text("🔹 شما هنوز هیچ مهارتی ثبت نکرده‌اید!", cid, cq.message.message_id, reply_markup=skills_menu_markup())
    else:
        msg = "🛠 <b>مهارت‌های شما:</b>\n" + "\n".join(
            [f"• {s['name']} ({s['category']}) — سطح: {s.get('proficiency', 1)}"
             for s in skills]
        )
        bot.edit_message_text(msg, cid, cq.message.message_id, parse_mode="HTML", reply_markup=skills_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_edit")
def skills_edit_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    skills = app.list_user_skills(user['id'])
    if not skills:
        bot.edit_message_text("شما مهارتی برای ویرایش ندارید.", cid, cq.message.message_id,
                                reply_markup=skills_menu_markup())
        return
    kb = InlineKeyboardMarkup()
    for s in skills:
        kb.add(InlineKeyboardButton(f"{s['name']} ({s['category']})", callback_data=f"edit_skill::{s['id']}"))

    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="menu_skills"))
    bot.edit_message_text("کدام مهارت را ویرایش کنیم؟", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("edit_skill::"))
def edit_skill_selected(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    skill_id = int(cq.data.split("::", 1)[1])
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    user_data[cid] = {"edit_skill_id": skill_id}
    push_state(cid, "edit_skill_name")
    bot.edit_message_text("نام جدید مهارت را بفرست:", cid, cq.message.message_id)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "edit_skill_name")
def edit_skill_name_handler(m):
    cid = m.chat.id
    name = (m.text or "").strip()
    if not name:
        send_and_remember(cid, "❌ نام نمی‌تواند خالی باشد.", reply_markup=nav_keyboard())
        return
    skill_id = user_data.get(cid, {}).get("edit_skill_id")
    if not skill_id:
        send_and_remember(cid, "خطا در شناسایی مهارت.", reply_markup=skills_menu_markup())
        reset_state(cid)
        return

    all_skills = app.list_all_skills()
    current_skill = next((s for s in all_skills if s['id'] == skill_id), None)
    if not current_skill:
        send_and_remember(cid, "مهارت مورد نظر یافت نشد.", reply_markup=skills_menu_markup())
        reset_state(cid)
        return
        # به‌روزرسانی
    ok = app.update_skill(skill_id, name, current_skill['category'])
    reset_state(cid)
    if ok:
        send_and_remember(cid, f"✅ مهارت به «{name}» ویرایش شد.", reply_markup=skills_menu_markup())
    else:
        send_and_remember(cid, "❌ ویرایش مهارت ناموفق بود.", reply_markup=skills_menu_markup())

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_delete")
def skills_delete_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    skills = app.list_user_skills(user['id'])
    if not skills:
        bot.edit_message_text("شما مهارتی برای حذف ندارید.", cid, cq.message.message_id,
                                reply_markup=skills_menu_markup())
        return
    kb = InlineKeyboardMarkup()
    for s in skills:
        kb.add(InlineKeyboardButton(f"{s['name']} ({s['category']})",
                                    callback_data=f"delete_skill::{s['id']}"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="menu_skills"))
    bot.edit_message_text("کدام مهارت را حذف کنیم؟", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("delete_skill::"))
def delete_skill_confirm(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    skill_id = int(cq.data.split("::", 1)[1])
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return

    user_data[cid] = {"delete_skill_id": skill_id}
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("بله، حذف شود", callback_data="confirm_delete_skill"),
        InlineKeyboardButton("خیر", callback_data="menu_skills")
    )
    bot.edit_message_text("آیا مطمئن هستید؟ این عمل غیرقابل بازگشت است.", cid, cq.message.message_id,
                            reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "confirm_delete_skill")
def confirm_delete_skill(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    skill_id = user_data.get(cid, {}).get("delete_skill_id")
    user = app.find_user(cid)
    if not user or not skill_id:
        bot.edit_message_text("خطا در حذف مهارت.", cid, cq.message.message_id,
                                reply_markup=skills_menu_markup())
        bot.answer_callback_query(cq.id)
        return
    ok = app.remove_user_skill(user['id'], skill_id)
    reset_state(cid)
    if ok:
        bot.edit_message_text("✅ مهارت با موفقیت حذف شد.", cid, cq.message.message_id,
                                reply_markup=skills_menu_markup())
    else:
        bot.edit_message_text("❌ حذف مهارت ناموفق بود.", cid, cq.message.message_id,
                                reply_markup=skills_menu_markup())
    bot.answer_callback_query(cq.id)

    skills = app.list_user_skills(user_id=user['id'])
    if not skills:
        bot.edit_message_text("🔹 شما هنوز هیچ مهارتی ثبت نکرده‌اید!", cid, cq.message.message_id,
                              reply_markup=skills_menu_markup())
    else:
        msg = "🛠 <b>لیست مهارت‌های شما:</b>\n" + "\n".join(
            [f"{idx+1}. {sk['name']} ({sk['category']}) — سطح: {sk.get('proficiency',1)}"
             for idx, sk in enumerate(skills)]
        )
        bot.edit_message_text(msg, cid, cq.message.message_id, parse_mode="HTML", reply_markup=skills_menu_markup())
    bot.answer_callback_query(cq.id)
# =========================
# Projects: منو + لیست + افزودن + فیلتر وضعیت
# =========================

def projects_menu_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ پروژه جدید", callback_data="prj_add"),
        InlineKeyboardButton("📋 لیست پروژه‌ها", callback_data="prj_list"),
        InlineKeyboardButton("📂 بر اساس وضعیت", callback_data="prj_by_status"),
    )
    # بازگشت‌ها
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"),
        InlineKeyboardButton("❓ راهنما", callback_data="menu_help"),
    )
    return kb

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_projects")
def menu_projects_cb(cq):
    """نمایش منوی پروژه‌ها (inline)"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'projects_menu')
    bot.edit_message_text("پروژه‌ها:", cid, cq.message.message_id, reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "prj_list")
def prj_list_cb(cq):
    """نمایش لیست همه پروژه‌های کاربر"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    show_typing(cid)
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    rows = app.get_projects_by_employer(user['id'])
    if not rows:
        bot.edit_message_text("هنوز پروژه‌ای ثبت نکرده‌اید.", cid, cq.message.message_id, reply_markup=projects_menu_markup())
        return
    lines = []
    for r in rows:
        st = STATUS_FA.get(r.get('status','draft'), r.get('status','draft'))
        prg = r.get('progress', 0)
        # === اضافه کردن آخرین بروزرسانی ===
        updated_at = r.get('updated_at') or r.get('created_at', '')
        if updated_at:
            updated_at = str(updated_at)[:16]  # YYYY-MM-DD HH:MM
            lines.append(f"• <b>{r['title']}</b> — {st} ({prg}%) — 🕒 {updated_at}")
        else:
            lines.append(f"• <b>{r['title']}</b> — {st} ({prg}%)")
    bot.edit_message_text("📋 <b>لیست پروژه‌ها</b>:\n" + "\n".join(lines),
                          cid, cq.message.message_id, parse_mode="HTML", reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "prj_by_status")
def prj_by_status_cb(cq):
    """نمایش فهرست وضعیت‌ها برای فیلتر پروژه‌ها"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    kb = InlineKeyboardMarkup(row_width=2)
    for s in STATUSES:
        kb.add(InlineKeyboardButton(STATUS_FA[s], callback_data=f"prj_status::{s}"))
    # بازگشت‌ها
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu_projects"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    bot.edit_message_text("فیلتر بر اساس وضعیت:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("prj_status::"))
def prj_status_filter_cb(cq):
    """نمایش پروژه‌ها بر اساس وضعیت انتخاب‌شده"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    show_typing(cid)
    st = cq.data.split("::",1)[1]
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    rows = app.projects_by_status(user['id'], st)
    if not rows:
        bot.edit_message_text(f"پروژه‌ای با وضعیت «{STATUS_FA.get(st, st)}» ندارید.",
                              cid, cq.message.message_id, reply_markup=projects_menu_markup())
        return
    items = []
    for r in rows:
        status_text = STATUS_FA.get(r['status'], r['status'])
        progress = r.get('progress', 0)
        # === اضافه کردن آخرین بروزرسانی ===
        updated_at = r.get('updated_at') or r.get('created_at', '')
        if updated_at:
            updated_at = str(updated_at)[:16]
            items.append(f"• <b>{r['title']}</b> — {status_text} ({progress}%) — 🕒 {updated_at}")
        else:
            items.append(f"• <b>{r['title']}</b> — {status_text} ({progress}%)")
    bot.edit_message_text("📂 پروژه‌ها بر اساس وضعیت:\n" + "\n".join(items),
                          cid, cq.message.message_id, parse_mode="HTML", reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "prj_add")
def prj_add_cb(cq):
    """شروع فرآیند افزودن پروژه (مرحله عنوان)"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu()); return
    user_data.setdefault(cid, {})['prj'] = {}
    push_state(cid, "prj_title")
    # در مسیرهای متنی، ReplyKeyboard بازگشت/خانه را نشان بده
    bot.edit_message_text("📝 عنوان پروژه را بفرست:", cid, cq.message.message_id)
    schedule_message_expiry(cid, cq.message.message_id, delay_seconds=3600)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "prj_title")
def prj_title_msg(m):
    """گرفتن عنوان پروژه و رفتن به مرحله توضیح"""
    cid = m.chat.id
    title = (m.text or "").strip()
    if not title:
        send_and_remember(cid, "❌ عنوان خالی است. دوباره بفرست.", reply_markup=nav_keyboard()); return
    user_data[cid]['prj']['title'] = title
    push_state(cid, "prj_desc")
    send_and_remember(cid, "📝 توضیحات کوتاه پروژه را بفرست:", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "prj_desc")
def prj_desc_msg(m):
    cid = m.chat.id
    desc = (m.text or "").strip()
    user_data[cid]['prj']['desc'] = desc
    push_state(cid, "prj_category")
    send_and_remember(cid, "دسته‌بندی پروژه را انتخاب کنید:", reply_markup=project_category_keyboard())

def project_category_keyboard():

    kb = InlineKeyboardMarkup(row_width=2)
    for cat in PROJECT_CATEGORIES:
        kb.add(InlineKeyboardButton(cat, callback_data=f"prjcat::{cat}"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_projects"))
    return kb

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("prjcat::"))
def prj_category_selected(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    category = cq.data.split("::", 1)[1]
    user_data[cid]['prj']['category'] = category
    push_state(cid, "prj_budget")
    bot.edit_message_text("بودجه پروژه (به تومان) را وارد کنید:", cid, cq.message.message_id, reply_markup=inline_nav_keyboard())
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "prj_budget")
def prj_budget_msg(m):
    cid = m.chat.id
    try:
        budget = float(m.text.strip())
        if budget <= 0:
            send_and_remember(cid, "❌ بودجه باید بیشتر از صفر باشد.", reply_markup=nav_keyboard())
            return
        user_data[cid]['prj']['budget'] = budget
        push_state(cid, "prj_days")
        send_and_remember(cid, "زمان تحویل پروژه (تعداد روز) را وارد کنید:", reply_markup=nav_keyboard())
    except ValueError:
        send_and_remember(cid, "❌ لطفاً یک عدد معتبر وارد کنید.", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == "prj_days")
def prj_days_msg(m):
    cid = m.chat.id
    try:
        days = int(m.text.strip())
        if days <= 0:
            send_and_remember(cid, "❌ تعداد روز باید بیشتر از صفر باشد.", reply_markup=nav_keyboard())
            return
        user_data[cid]['prj']['days'] = days
        user = app.find_user(cid)
        prj = user_data[cid]['prj']

        # === ذخیره موقت برای تأیید ===
        user_data[cid]['confirm_project'] = {
            'employer_id': user['id'],
            'title': prj['title'],
            'description': prj.get('desc'),
            'category': prj.get('category'),
            'budget': prj.get('budget'),
            'delivery_days': days
        }

        # === پیش‌نمایش پروژه ===
        preview = (
            f"✅ <b>پیش‌نمایش پروژه</b>\n"
            f"عنوان: {prj['title']}\n"
            f"توضیح: {prj.get('desc', '-')}\n"
            f"دسته: {prj.get('category', '-')}\n"
            f"بودجه: {prj.get('budget', '-')} تومان\n"
            f"زمان تحویل: {days} روز"
        )

        # === دکمه‌های تأیید/لغو ===
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ تأیید و ثبت", callback_data="confirm_project_yes"),
            InlineKeyboardButton("❌ لغو", callback_data="confirm_project_no")
        )

        bot.send_message(cid, preview, parse_mode="HTML", reply_markup=kb)

    except ValueError:
        send_and_remember(cid, "❌ لطفاً یک عدد صحیح وارد کنید.", reply_markup=nav_keyboard())


# =========================
# Dashboard & Reports
# =========================

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_dashboard")
def dashboard_cb(cq):
    """خلاصه داشبورد: شمارش پروژه‌ها، تفکیک وضعیت‌ها، مهارت‌ها، بودجه و درصد تکمیل پروفایل"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    show_typing(cid)
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return

    # === درصد تکمیل پروفایل ===
    completion = _profile_completion_percent(user)

    stats = app.dashboard_stats(user['id'])
    by = stats['by_status']
    bsum = stats['budget_sum'] or 0
    bavg = stats['budget_avg'] or 0
    # خلاصهٔ Top Skills (3 مورد)
    top = app.get_top_skills(user['id'], limit=3) or []
    top_line = "، ".join([f"{t['name']} (x{t['uses']})" for t in top]) if top else "-"

    text = (
        "📊 <b>داشبورد شما</b>\n"
        f"✅ تکمیل پروفایل: <b>{completion}%</b>\n"
        f"📁 پروژه‌ها: <b>{stats['projects_total']}</b>\n"
        f"   ├ 🟢 باز: {by['open']} | 🟠 درحال‌انجام: {by['in_progress']}\n"
        f"   └ ✅ تمام‌شده: {by['done']} | ❌ لغوشده: {by['cancelled']} | 📝 پیشنویس: {by['draft']}\n"
        f"🛠 مهارت‌ها: <b>{stats['skills_total']}</b>\n"
        f"💵 بودجه: جمع {bsum} | میانگین {bavg}\n"
        f"⭐ Top Skills: {top_line}\n"
    )
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🟢 باز", callback_data="dash_filter_open"),
        InlineKeyboardButton("🟠 درحال‌انجام", callback_data="dash_filter_in_progress"),
        InlineKeyboardButton("✅ تمام‌شده", callback_data="dash_filter_done"),
    )
    kb.add(
        InlineKeyboardButton("❌ لغوشده", callback_data="dash_filter_cancelled"),
        InlineKeyboardButton("📝 پیشنویس", callback_data="dash_filter_draft"),
        InlineKeyboardButton("📈 گزارش بیشتر", callback_data="dash_more")
    )
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    YOUR_TELEGRAM_ID = 818973364
    if cid == YOUR_TELEGRAM_ID:
        total_users = app.count_all_users()
        text += f"👥 کاربران کل: {total_users}\n"
    bot.edit_message_text(text, cid, cq.message.message_id, parse_mode="HTML", reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("dash_filter_"))
def dash_filter_projects(cq):
    """فهرست پروژه‌ها بر اساس وضعیت از داشبورد"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    status = cq.data.replace("dash_filter_", "")
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید."); return
    projects = app.projects_by_status(user['id'], status)
    if not projects:
        bot.edit_message_text(f"هیچ پروژه‌ای با وضعیت «{STATUS_FA.get(status,status)}» یافت نشد.",
                              cid, cq.message.message_id, reply_markup=main_menu())
    else:
        lines = []
        for i, p in enumerate(projects, 1):
            lines.append(f"{i}. {p['title']} — {STATUS_FA.get(p['status'], p['status'])} ({p.get('progress',0)}%)")
        msg = "📁 پروژه‌ها:\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup()
        for p in projects[:10]:
            kb.add(InlineKeyboardButton(f"تغییر وضعیت: {p['title']}", callback_data=f"proj_setstatus_{p['id']}"))
        # بازگشت/خانه
        kb.add(
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu_dashboard"),
            InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
        )
        bot.edit_message_text(msg, cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "confirm_project_yes")
def confirm_project_yes(cq):
    cid = cq.message.chat.id
    # ✅ دریافت داده با .get() برای جلوگیری از KeyError
    project_data = user_data.get(cid, {}).get('confirm_project')
    if not project_data:  # ← اینجا اصلاح شد: project_data نه project_
        bot.answer_callback_query(cq.id, "❌ داده پروژه یافت نشد. لطفاً دوباره پروژه ایجاد کنید.")
        try:
            bot.edit_message_text(
                "❌ داده پروژه منقضی یا ناموجود است.",
                cid, cq.message.message_id,
                reply_markup=projects_menu_markup()
            )
        except Exception:
            pass
        return

    # ✅ ثبت پروژه
    prj_id = app.add_project(**project_data)
    reset_state(cid)
    # ✅ حذف ایمن داده موقت
    if cid in user_data:
        user_data[cid].pop('confirm_project', None)

    # ✅ نمایش نتیجه
    title = project_data['title']
    if prj_id and prj_id != "DUPLICATE":
        msg = f"✅ پروژه «{title}» با موفقیت ایجاد شد."
    elif prj_id == "DUPLICATE":
        msg = "⚠️ عنوان پروژه تکراری است."
    else:
        msg = "❌ خطایی در ایجاد پروژه رخ داد."

    try:
        bot.edit_message_text(msg, cid, cq.message.message_id, reply_markup=projects_menu_markup())
    except Exception:
        pass
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "confirm_project_no")
def confirm_project_no(cq):
    cid = cq.message.chat.id
    reset_state(cid)
    if cid in user_data:
        user_data[cid].pop('confirm_project', None)

    bot.edit_message_text(
        "❌ ثبت پروژه لغو شد.",
        cid, cq.message.message_id,
        reply_markup=projects_menu_markup()
    )
    bot.answer_callback_query(cq.id)


@bot.callback_query_handler(func=lambda cq: cq.data == "dash_more")
def dashboard_more_cb(cq):
    """گزارش تکمیلی: Top skills (۱۰تایی)، بودجهٔ انجام‌شده، آخرین پروژه‌ها"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید."); return

    top = app.get_top_skills(user['id'], limit=10) or []
    bstats = app.budget_stats(user['id'])
    recents = app.recent_projects(user['id'], limit=5) or []

    top_lines = [f"• {i+1}. {t['name']} — دسته: {t['category']} — دفعات: {t['uses']} — میانگین مهارت: {round(t['avg_prof'] or 0,1)}"
                 for i, t in enumerate(top)] or ["(هیچ)"]

    r_lines = [f"• {i+1}. {p['title']} — {STATUS_FA.get(p['status'], p['status'])} — {p.get('progress',0)}% "
               f"(بودجه: {p['budget'] or '-'}, آخرین بروزرسانی: {str(p.get('updated_at') or p.get('created_at'))[:19]})"
               for i, p in enumerate(recents)] or ["(هیچ)"]

    text = (
        "<b>📈 گزارش تکمیلی</b>\n\n"
        "<b>Top Skills (تا ۱۰ مورد):</b>\n" + "\n".join(top_lines) + "\n\n"
        "<b>بودجه:</b>\n"
        f"• میانگین کل: {bstats['avg_all'] or '-'} | جمع کل: {bstats['sum_all'] or '-'}\n"
        f"• میانگین تمام‌شده: {bstats['avg_done'] or '-'} | جمع تمام‌شده: {bstats['sum_done'] or '-'} | تعداد تمام‌شده: {bstats['count_done']}\n\n"
        "<b>آخرین پروژه‌ها:</b>\n" + "\n".join(r_lines)
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔙 بازگشت به داشبورد", callback_data="menu_dashboard"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    bot.edit_message_text(text, cid, cq.message.message_id, parse_mode="HTML", reply_markup=kb)
    bot.answer_callback_query(cq.id)
# =========================
# Profile: نمایش و ویرایش با دکمه‌های بازگشت/خانه
# =========================

def profile_menu_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ ویرایش نام", callback_data="profile_edit::name"),
        InlineKeyboardButton("✏️ ویرایش ایمیل", callback_data="profile_edit::email"),
        InlineKeyboardButton("✏️ ویرایش نقش", callback_data="profile_edit::role"),
        InlineKeyboardButton("🖼 آپلود عکس پروفایل", callback_data="profile_edit::profile_picture"),
        InlineKeyboardButton("⭐ ویرایش رتبه", callback_data="profile_edit::rating"),
        InlineKeyboardButton("🔑 تغییر رمز عبور", callback_data="profile_edit::password"),
    )
    kb.add(
        InlineKeyboardButton("✏️ ویرایش بیو", callback_data="profile_edit::bio"),
        InlineKeyboardButton("✏️ ویرایش نرخ ساعتی", callback_data="profile_edit::hourly_rate"),
    )
    kb.add(
        InlineKeyboardButton("✏️ لینکداین", callback_data="profile_edit::linkedin"),
        InlineKeyboardButton("✏️ گیت‌هاب", callback_data="profile_edit::github"),
    )
    kb.add(
        InlineKeyboardButton("✏️ وب‌سایت", callback_data="profile_edit::website"),
        InlineKeyboardButton("✏️ تلفن", callback_data="profile_edit::phone"),
    )
    # دکمه‌های بازگشت/خانه
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"),
        InlineKeyboardButton("❓ راهنما", callback_data="menu_help"),

    )
    return kb

def _profile_text(u: dict) -> str:
    return (
        "👤 <b>پروفایل شما</b>\n"
        f"• نام: {u.get('name','-')}\n"
        f"• ایمیل: {u.get('email','-')}\n"
        f"• نقش: {u.get('role','-')}\n"
        f"• بیو: {u.get('bio','-')}\n"
        f"• نرخ ساعتی: {u.get('hourly_rate','-')}\n"
        f"• تلفن: {u.get('phone','-')}\n"
        f"• LinkedIn: {u.get('linkedin','-')}\n"
        f"• GitHub: {u.get('github','-')}\n"
        f"• Website: {u.get('website','-')}\n"
        f"• 🆔 شناسه تلگرام: <code>{u.get('telegram_id','-')}</code>\n"
    )

def show_profile(cq_or_msg):
    """
    نمایش پروفایل کاربر — با پشتیبانی از عکس پروفایل (file_id) و رتبه (rating).
    """
    if hasattr(cq_or_msg, "message"):  # CallbackQuery
        cid = cq_or_msg.message.chat.id
        mid_to_edit = cq_or_msg.message.message_id
    else:  # Message
        cid = cq_or_msg.chat.id
        mid_to_edit = None

    user = app.find_user(cid)
    if not user:
        if mid_to_edit:
            bot.edit_message_text("ابتدا وارد شوید.", cid, mid_to_edit, reply_markup=main_menu())
        else:
            send_and_remember(cid, "ابتدا وارد شوید.", reply_markup=main_menu())
        return

    # --- ساخت متن پروفایل با رتبه ---
    rating = user.get('rating')
    rating_str = f"{rating:.2f} ⭐" if rating is not None else "—"
    profile_text = (
        "👤 <b>پروفایل شما</b>\n"
        f"• نام: {user.get('name', '-')}\n"
        f"• ایمیل: {user.get('email', '-')}\n"
        f"• نقش: {user.get('role', '-')}\n"
        f"• رتبه: {rating_str}\n"
        f"• بیو: {user.get('bio', '-')}\n"
        f"• نرخ ساعتی: {user.get('hourly_rate', '-')}\n"
        f"• تلفن: {user.get('phone', '-')}\n"
        f"• LinkedIn: {user.get('linkedin', '-')}\n"
        f"• GitHub: {user.get('github', '-')}\n"
        f"• Website: {user.get('website', '-')}\n"
    )

    photo_file_id = user.get('profile_picture')

    # --- اگر عکس وجود دارد ---
    if photo_file_id:
        try:
            # ارسال عکس و دریافت message_id
            msg = bot.send_photo(
                chat_id=cid,
                photo=photo_file_id,
                caption=profile_text,
                parse_mode="HTML",
                reply_markup=profile_menu_markup()
            )
            # ذخیره message_id جدید برای مدیریت بعدی
            _remember_last(cid, msg.message_id)

            # پاک کردن پیام قبلی (اگر از inline بوده)
            if mid_to_edit:
                try:
                    bot.delete_message(cid, mid_to_edit)
                except Exception:
                    pass
            return
        except Exception as e:
            logger.warning(f"Failed to send profile photo for user {cid}: {e}")

    # --- اگر عکس نبود یا خطا داد ---
    if mid_to_edit:
        bot.edit_message_text(
            text=profile_text,
            chat_id=cid,
            message_id=mid_to_edit,
            parse_mode="HTML",
            reply_markup=profile_menu_markup()
        )
        _remember_last(cid, mid_to_edit)
    else:
        msg = send_and_remember(cid, profile_text, parse_mode="HTML", reply_markup=profile_menu_markup())
        # send_and_remember خودش message_id رو ذخیره می‌کنه، ولی برای اطمینان:
        if msg:
            _remember_last(cid, msg.message_id)
            
@bot.callback_query_handler(func=lambda cq: cq.data == "menu_profile")
def menu_profile_cb(cq):
    """نمایش پروفایل با منوی ویرایش + دکمه‌های بازگشت/خانه"""
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(cq.id)
        return
    bot.edit_message_text(_profile_text(user), cid, cq.message.message_id, parse_mode="HTML",
                          reply_markup=profile_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("profile_edit::"))
def profile_edit_ask(cq):
    """
    انتخاب فیلد برای ویرایش (با ReplyKeyboard برای متن‌های مرحله‌ای).
    state = 'editprofile_wait' و field در user_data[cid]['editprofile_field']
    """
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید.")
        return
    _, field = cq.data.split("::", 1)
    user_data.setdefault(cid, {})["editprofile_field"] = field
    push_state(cid, 'editprofile_wait')

    # پیام درخواست مقدار جدید
    prompt_map = {
        "name": "نام جدید را بفرست:",
        "email": "ایمیل جدید را بفرست:",
        "role": "نقش را وارد کن (employer/freelancer):",
        "bio": "متن بیو را بفرست:",
        "hourly_rate": "نرخ ساعتی (عدد) را بفرست:",
        "linkedin": "آدرس LinkedIn را بفرست:",
        "github": "آدرس GitHub را بفرست:",
        "website": "آدرس وب‌سایت را بفرست:",
        "phone": "شماره تلفن را بفرست:",
         "profile_picture": "لطفاً یک عکس پروفایل بفرستید (به‌صورت تصویر، نه متن).",
        "rating": "رتبه‌بندی (عدد بین 0.00 تا 5.00) را وارد کن:",
        "password": "رمز عبور جدید (حداقل ۶ کاراکتر) را وارد کن:",
    }
    prompt = prompt_map.get(field, f"مقدار جدید برای {field} را بفرست:")
    bot.edit_message_text(f"✏️ {prompt}", cid, cq.message.message_id)
    schedule_message_expiry(cid, cq.message.message_id, delay_seconds=3600)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == 'editprofile_wait')
def profile_edit_save(m):
    """ذخیره مقدار جدید فیلد انتخاب‌شده و بازگشت به منوی پروفایل"""
    cid = m.chat.id
    user = app.find_user(cid)
    if not user:
        send_and_remember(cid, "ابتدا وارد شوید.", reply_markup=main_menu())
        reset_state(cid)
        return

    field = user_data.get(cid, {}).get("editprofile_field")
    if not field:
        send_and_remember(cid, "فیلد نامشخص است؛ دوباره از منوی پروفایل تلاش کن.", reply_markup=main_menu())
        reset_state(cid)
        return

    val = (m.text or "").strip()

    # --- اعتبارسنجی ایمیل ---
    if field == "email":
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', val):
            send_and_remember(cid, "❌ فرمت ایمیل نامعتبر است. لطفاً یک ایمیل معتبر وارد کنید (مثل: user@example.com).", reply_markup=nav_keyboard())
            return

    # --- اعتبارسنجی آدرس‌های وب (website, github, linkedin) ---
    elif field in ("website", "github", "linkedin"):
        if not re.match(r'^https?://', val):
            val = 'https://' + val
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}'
            r'|localhost'
            r'|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        if not url_pattern.match(val):
            send_and_remember(cid, "❌ لطفاً یک آدرس معتبر وارد کنید (مثل: github.com/yourname یا linkedin.com/in/you).", reply_markup=nav_keyboard())
            return

    # --- اعتبارسنجی شماره تلفن ---
    elif field == "phone":
        if not re.match(r'^[+\-\s()]*[0-9][+\-\s()0-9]*$', val):
            send_and_remember(cid, "❌ شماره تلفن نامعتبر است. فقط اعداد و نمادهای مجاز (+, -, فاصله، پرانتز) مجاز هستند.", reply_markup=nav_keyboard())
            return

    # --- اعتبارسنجی نرخ ساعتی ---
    elif field == "hourly_rate":
        try:
            val_float = float(val)
            if val_float < 0:
                send_and_remember(cid, "❌ نرخ ساعتی نمی‌تواند منفی باشد.", reply_markup=nav_keyboard())
                return
        except (TypeError, ValueError):
            send_and_remember(cid, "❌ فقط عدد معتبر برای نرخ ساعتی.", reply_markup=nav_keyboard())
            return

    # --- اعتبارسنجی نقش ---
    elif field == "role" and val not in ("employer", "freelancer"):
        send_and_remember(cid, "نقش باید employer یا freelancer باشد.", reply_markup=nav_keyboard())
        return

    # === پیش‌نمایش پروفایل ===
    updated_user = {**user, field: val}
    preview = _profile_text(updated_user)
    bot.send_message(cid, f"✅ <b>پیش‌نمایش پروفایل</b>\n{preview}", parse_mode="HTML")
    time.sleep(1)  # کمی تأخیر برای خوانایی

    # === ذخیره نهایی ===
    ok = app.update_user_profile(user['id'], field, val)
    reset_state(cid)

    if ok:
        send_and_remember(cid, "✅ ذخیره شد.", reply_markup=profile_menu_markup())
    else:
        send_and_remember(cid, "❌ خطا در ذخیره.", reply_markup=profile_menu_markup())
#=========================
# Auth: Register / Login (روتینگ به توابع موجود)
# =========================

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_register")
def menu_register_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    tg = cq.from_user.id
    existing_user = app.find_user(tg)
    if existing_user:
        bot.edit_message_text(
            "شما قبلاً ثبت‌نام کرده‌اید ✅",
            cid, cq.message.message_id,
            reply_markup=main_menu()
        )
        bot.answer_callback_query(cq.id)
        return

    gen_email = f"tg_{cid}@example.local"
    name = (cq.from_user.first_name or "کاربر") + ((" " + cq.from_user.last_name) if cq.from_user.last_name else "")
    role = "freelancer"
    temp_password = secrets.token_urlsafe(16)
    uid = app.add_user(
        telegram_id=tg,
        name=(name or "کاربر").strip(),
        email=gen_email,
        password_hash=temp_password,
        role=role
    )
    if uid:
        # به‌روزرسانی last_login
        app.update_user_profile(uid, "last_login", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        # ارسال رمز + دکمه ادامه
        bot.edit_message_text(
            "✅ <b>ثبت‌نام شما با موفقیت انجام شد!</b>\n\n"
            "🔑 رمز عبور موقت شما در پیام بعدی ارسال می‌شود.\n"
            "📌 <i>توصیه:</i> آن را در اولین فرصت تغییر دهید!",
            cid, cq.message.message_id,
            parse_mode="HTML"
        )
        bot.send_message(cid, f"<b>رمز عبور موقت:</b> <code>{temp_password}</code>", parse_mode="HTML")
        # دکمهٔ «ادامه»
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("➡️ ادامه", callback_data="back_to_menu"))
        bot.send_message(cid, "برای شروع، روی دکمهٔ زیر کلیک کنید:", reply_markup=kb)
    else:
        bot.edit_message_text(
            "❌ ثبت‌نام ناموفق بود.",
            cid, cq.message.message_id,
            reply_markup=main_menu()
        )
    schedule_message_expiry(cid, cq.message.message_id, delay_seconds=3600)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_login")
def menu_login_cb(cq):
    cid = cq.message.chat.id
    last_bot_message_id[cid] = cq.message.message_id
    u = app.find_user(cid)
    if u:
        name = (u.get("name") or "کاربر").strip()
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
        )
        bot.edit_message_text(f"✅ شما قبلاً وارد شده‌اید: <b>{name}</b>", cid, cq.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
        bot.answer_callback_query(cq.id); return
    # اگر وارد نیستی → پیشنهاد ثبت‌نام
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
       InlineKeyboardButton("📋 ثبت‌نام", callback_data="menu_register"),
       InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    bot.edit_message_text("حسابی پیدا نشد. برای ادامه «ثبت‌نام» را بزن.", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

def _register_exit_hooks():
    # Ctrl+C
    signal.signal(signal.SIGINT, interactive_exit_handler)
    # Stop/Terminate
    try:
        signal.signal(signal.SIGTERM, interactive_exit_handler)
    except Exception:
        pass
    atexit.register(lambda: None)

def schedule_message_expiry(chat_id: int, message_id: int, delay_seconds: int = 3600):
    """
    پیام را پس از delay_seconds ثانیه پاک می‌کند (پیش‌فرض: ۱ ساعت).
    """
    def _expire():
        time.sleep(delay_seconds)
        with EXPIRY_LOCK:
            key = (chat_id, message_id)
            if key in EXPIRING_MESSAGES:
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    pass  # ممکن است پیام قبلاً پاک شده باشد
                finally:
                    EXPIRING_MESSAGES.pop(key, None)

    with EXPIRY_LOCK:
        EXPIRING_MESSAGES[(chat_id, message_id)] = time.time() + delay_seconds

    threading.Thread(target=_expire, daemon=True).start()

def cancel_message_expiry(chat_id: int, message_id: int):
    """لغو پاک‌کردن خودکار پیام (در صورت نیاز)"""
    with EXPIRY_LOCK:
        EXPIRING_MESSAGES.pop((chat_id, message_id), None)

# ==================== HEALTHCHECK =====================
def startup_healthcheck():
    """
    بررسی سلامت سیستم در زمان راه‌اندازی — نسخه اصلاح‌شده بدون اتصال جداگانه
    """
    print("\n" + "═" * 58)
    print("🚀 TaskBot starting… running healthchecks")
    print("═" * 58)
    # 1) Telegram API
    try:
        me = bot.get_me()
        print(f"✅ Telegram: connected as @{getattr(me, 'username', '?')} (id={getattr(me, 'id', '?')})")
        log_kv(action='startup_telegram', user=getattr(me, 'username', '?'))
    except Exception as e:
        print(f"❌ Telegram: getMe failed: {e}")
        raise
    # 2) DB connectivity via db_manager (همان سیستم اصلی)
    try:
        db_manager.execute_query("SELECT 1")
        print("✅ Database: connection OK (via db_manager)")
        log_kv(action='startup_db', user='system')
    except Exception as e:
        print(f"❌ Database: connection failed: {e}")
        raise
    # 3) Tables check
    try:
        tables = db_manager.execute_query("SHOW TABLES")
        table_names = {row['Tables_in_task_manager'] for row in tables}
        missing = [t for t in ("tasks", "users") if t not in table_names]
        if missing:
            print(f"⚠️ Schema: missing tables -> {', '.join(missing)}")
        else:
            print("✅ Schema: tables [tasks, users] found")
    except Exception as e:
        print(f"❌ Schema: check failed: {e}")
    print("✅ All checks done. Bot is ready.")
    print("═" * 58 + "\n")
    log_kv(action='startup_ready', user='system')


if __name__ == "__main__":
    _register_exit_hooks()
    signal.signal(signal.SIGINT, interactive_exit_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, interactive_exit_handler)  # kill/stop from IDE or OS
    logger.info("Bot polling started…")
    bot.polling(non_stop=True, interval=1, timeout=30, long_polling_timeout=30)


# =========================
# Imports & Bootstrapping
# =========================
last_bot_message_id: dict[int, int] = {}

import logging, os, re, time
from typing import Dict, Any, List
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
import telebot
from telebot import apihelper
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 60

from CONFIG import Config
from Database import FreelanceBot

# لاگ‌ها
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# اپ و بات (اینا رو فقط همین‌جا می‌سازیم؛ اگر پایین‌تر هم ساختی فعلاً دست نزن، بعداً فقط گروه‌بندی می‌کنیم)
app: FreelanceBot = FreelanceBot()
bot = telebot.TeleBot(Config.API_TOKEN, parse_mode="HTML")
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
# ==== Lightweight session layer for switching user & logout ====

session_override: dict[int, int] = {}
# چت‌هایی که عمداً از حساب خارج شده‌اند (find_user باید None برگرداند)
logged_out: set[int] = set()

# نسخه‌ی خامِ find_user را نگه می‌داریم تا بعداً صدا بزنیم
if not hasattr(app, "find_user_orig"):
    app.find_user_orig = app.find_user

def _find_user_patched(telegram_id: int):
    """هرجا app.find_user صدا زده می‌شود، این نسخه اولویت دارد."""
    # اگر کاربر logout کرده باشد:
    if telegram_id in logged_out:
        return None
    # اگر کاربر در این چت روی یک حساب دیگر سوییچ کرده باشد:
    if telegram_id in session_override:
        try:
            # باید در Database.py یک متد get_user_by_id داشته باشی (رَپر روی DQL)
            return app.get_user_by_id(session_override[telegram_id])
        except Exception:
            # اگر متد بالا هنوز نداری، این except مانع کرش می‌شود و می‌افتد به نسخه‌ی خام
            pass
    # حالت عادی: همون رفتار اصلی
    return app.find_user_orig(telegram_id)  # type: ignore

# مونکی‌پچ: از این لحظه به بعد، همه‌ی جاهایی که app.find_user را صدا می‌زنند
# این منطق جدید را می‌بینند (سوییچ حساب و logout اعمال می‌شود).
app.find_user = _find_user_patched  # type: ignore
# ==============================================================

# Constants
# =========================
MAX_ACCOUNTS_PER_TELEGRAM = 2

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

def send_and_remember(cid, text, **kwargs):
    """پیامی می‌فرستد و id آخرین پیام ارسالی را نگه می‌دارد تا بتوانیم بعداً پاک/ویرایش کنیم."""
    if cid in last_bot_message_id:
        try: bot.delete_message(cid, last_bot_message_id[cid])
        except: pass
    msg = bot.send_message(cid, text, **kwargs)
    last_bot_message_id[cid] = msg.message_id
    return msg
def show_login_accounts(message):
    """
    Placeholder: نمایش لیست حساب‌ها یا پیام ورود
    این نسخه فقط برای جلوگیری از خطا اضافه شده
    """
    cid = message.chat.id
    bot.send_message(cid, "🔐 لطفا نام کاربری و گذرواژه خود را وارد کنید یا ثبت‌نام کنید.",
                     reply_markup=main_menu())

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
        InlineKeyboardButton("🔑 ورود",    callback_data="menu_login"),
        InlineKeyboardButton("🛠 مهارت‌ها", callback_data="menu_skills"),
        InlineKeyboardButton("📁 پروژه‌ها", callback_data="menu_projects"),
        InlineKeyboardButton("👤 پروفایل من", callback_data="menu_profile"),
        InlineKeyboardButton("❓ راهنما",   callback_data="menu_help"),
        InlineKeyboardButton("📊 داشبورد",  callback_data="menu_dashboard"),
        InlineKeyboardButton("🔁 سوییچ حساب", callback_data="switch_my_account"),
        InlineKeyboardButton("👤 حساب‌های من", callback_data="show_my_accounts"),
        )
    # لینک پشتیبانی که قبلاً هم داشتی، اگر می‌خوای نگه‌دار:
    kb.add(InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/Anakin9495"))
    # دکمهٔ بازگشت به خانه (inline) – این، پیام فعلی رو به منوی اصلی برمی‌گردونه
    kb.add(InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_menu"))
    return kb

def accounts_list_markup(users) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        title = (u.get("name") or "کاربر").strip()
        tg = u.get("telegram_id") or "-"
        kb.add(InlineKeyboardButton(
            f"{title} — tg:{tg}  (#ID {u['id']})",
            callback_data=f"login_select::{u['id']}"
        ))
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"),
    )
    return kb


# ===== Lightweight cmd_* shims to avoid "undefined" and make demo work =====
def cmd_register(message):
    """ثبت‌نام سریع: اگر کاربر نبود، می‌سازیم؛ اگر بود، پیام می‌دهیم."""
    cid = message.chat.id
    u = app.find_user(cid)
    if u:
        bot.send_message(cid, "شما قبلاً ثبت‌نام کرده‌اید ✅", reply_markup=main_menu()); return
    # به خاطر UNIQUE بودن ایمیل، یک ایمیل یکتا بر اساس telegram_id می‌سازیم
    gen_email = f"tg_{cid}@example.local"
    name = (message.from_user.first_name or "کاربر") + ((" " + message.from_user.last_name) if message.from_user.last_name else "")
    uid = app.add_user(telegram_id=cid, name=(name or "کاربر").strip(), email=gen_email, password_hash="", role="freelancer")
    if uid:
        bot.send_message(cid, "ثبت‌نام سریع انجام شد ✅", reply_markup=main_menu())
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

def cmd_help(message):
    cid = message.chat.id
    bot.send_message(cid, "راهنما:\n- از منوی بالا بخش‌ها را انتخاب کنید.\n- برای برگشت از «🔙 بازگشت» و «🏠 منوی اصلی» استفاده کنید.", reply_markup=main_menu())
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

# =========================
# Global Back (Inline) — بازگشت به منوی اصلی
# =========================
@bot.callback_query_handler(func=lambda cq: cq.data == "back_to_menu")
def back_to_menu_cb(cq):
    """برگشت inline به خانه (وقتی داخل منوهای inline هستیم)."""
    cid = cq.message.chat.id
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
    users = app.list_users_by_telegram_id(cid, limit=10)  # ← جدید
    if users:
        name = (users[0].get("name") or "کاربر").strip()
        txt = (
            f"سلام {m.from_user.first_name}!\n"
            f"⚠️ به نظر می‌رسه قبلاً ثبت‌نام کرده‌ای.\n"
            f"اولین حساب یافت‌شده: <b>{name}</b>\n\n"
            "می‌خوای مستقیم وارد یکی از حساب‌های قبلی‌ات بشی؟"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👤 نمایش حساب‌های من", callback_data="show_my_accounts"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_menu")
        )
        bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb)
    else:
        bot.send_message(
            cid,
            f"سلام {m.from_user.first_name}!\nبرای ادامه یکی از گزینه‌ها را لمس کن:",
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
    elif action == "help":     globals().get("cmd_help", lambda x: bot.send_message(cid, "تابع cmd_help تعریف نشده است.", reply_markup=main_menu()))(cq.message)
    elif action == "dashboard": dashboard_cb(cq)  # اگر نسخهٔ جدا هم داری، هر دو می‌مانند (حذف نمی‌کنیم)
    elif action == "profile":   globals().get("show_profile", lambda x: bot.send_message(cid, "تابع show_profile تعریف نشده است.", reply_markup=main_menu()))(cq)
    bot.answer_callback_query(cq.id)
# =========================
# Skills: منو + افزودن/لیست
# =========================
def skills_menu_markup() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ افزودن", callback_data="skills_add"),
      InlineKeyboardButton("📋 لیست",   callback_data="skills_list"),
      InlineKeyboardButton("✏️ ویرایش", callback_data="skills_edit"),
      InlineKeyboardButton("🗑 حذف",    callback_data="skills_delete")
    )
    # دکمهٔ بازگشت به خانه (inline)
    kb.add(InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_menu"))
    return kb

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("login_select::"))
def login_select_cb(cq):
    cid = cq.message.chat.id
    try:
        uid = int(cq.data.split("::", 1)[1])
    except:
        bot.answer_callback_query(cq.id, "شناسه نامعتبر"); return

    try:
        session_override[cid] = uid
        logged_out.discard(cid)
    except: pass

    bot.edit_message_text(f"✅ وارد حساب #ID {uid} شدی.", cid, cq.message.message_id,
                          reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "show_my_accounts")
def show_my_accounts_cb(cq):
    cid = cq.message.chat.id
    users = app.list_users_by_telegram_id(cid, limit=20)
    if not users:
        bot.edit_message_text("حسابی با این تلگرام یافت نشد.", cid, cq.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(cq.id); return
    bot.edit_message_text("حساب‌های مرتبط با تلگرام شما:", cid, cq.message.message_id,
                          reply_markup=accounts_list_markup(users))
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "switch_my_account")
def switch_my_account_cb(cq):
    cid = cq.message.chat.id
    users = app.list_users_by_telegram_id(cid, limit=20)
    if not users:
        bot.edit_message_text("حسابی برای این تلگرام پیدا نشد.", cid, cq.message.message_id, reply_markup=main_menu())
    elif len(users) < 2:
        bot.edit_message_text("فقط یک حساب داری. برای سوییچ، ابتدا حساب دوم را بساز.", cid, cq.message.message_id,
                              reply_markup=main_menu())
    else:
        bot.edit_message_text("یکی از حساب‌ها را انتخاب کن:", cid, cq.message.message_id,
                              reply_markup=accounts_list_markup(users))
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "proceed_register_new")
def proceed_register_new_cb(cq):
    cid = cq.message.chat.id

    # enforce سقف
    count = app.count_users_by_telegram_id(cid)
    if count >= MAX_ACCOUNTS_PER_TELEGRAM:
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👤 حساب‌های من", callback_data="show_my_accounts"),
            InlineKeyboardButton("🔁 سوییچ حساب", callback_data="switch_my_account"),
        )
        bot.edit_message_text(
            f"⚠️ به سقف {MAX_ACCOUNTS_PER_TELEGRAM} حساب رسیدی؛ امکان ساخت حساب جدید نیست.",
            cid, cq.message.message_id, reply_markup=kb
        )
        bot.answer_callback_query(cq.id); return

    # نقش پیشنهادی برای حساب دوم: اگر یکی freelancer داری، این یکی employer و برعکس
    users = app.list_users_by_telegram_id(cid, limit=20)
    roles_have = { (u.get("role") or "").lower() for u in users }
    next_role = "employer" if "freelancer" in roles_have else "freelancer"

    gen_email = f"tg_{cid}_{int(time.time())}@example.local"
    name = (cq.from_user.first_name or "کاربر") + ((" " + cq.from_user.last_name) if cq.from_user.last_name else "")

    uid = app.add_user(telegram_id=cid, name=(name or "کاربر").strip(),
                       email=gen_email, password_hash="", role=next_role)
    if uid:
        try:
            session_override[cid] = uid  # بعد از ساخت، روی همین حساب جدید سوییچ کن
            logged_out.discard(cid)
        except: pass
        bot.edit_message_text(f"✅ حساب جدید با نقش {next_role} ساخته شد و وارد شدی.", cid, cq.message.message_id,
                              reply_markup=main_menu())
    else:
        bot.edit_message_text("❌ ساخت حساب جدید ناموفق بود.", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)


@bot.callback_query_handler(func=lambda cq: cq.data == "menu_skills")
def menu_skills_cb(cq):
    """نمایش منوی مهارت‌ها (inline)"""
    cid = cq.message.chat.id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'skills_menu')
    bot.edit_message_text("مهارت‌ها:", cid, cq.message.message_id, reply_markup=skills_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_add")
def skills_add_cb(cq):
    """نمایش دسته‌بندی‌ها برای افزودن مهارت جدید"""
    cid = cq.message.chat.id
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"skillcat_{idx}") for idx, cat in enumerate(SKILL_CATEGORIES)]
    for i in range(0, len(buttons), 2):
        kb.add(*buttons[i:i+2])
    # دکمهٔ بازگشت به منوی مهارت‌ها
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="menu_skills"))
    # و بازگشت به خانه
    kb.add(InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu"))
    bot.edit_message_text("دسته‌بندی مهارت را انتخاب کنید:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_list")
def skills_list_cb(cq):
    """نمایش لیست مهارت‌های کاربر"""
    cid = cq.message.chat.id
    show_typing(cid)
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return

    # نسخه‌های متفاوت از این بخش در فایل‌ت وجود داشت؛ اینجا همان منطق را نگه‌می‌داریم
    # و فقط خروجی را با کیبورد منظم نمایش می‌دهیم.
    uid = user.get('id') if isinstance(user, dict) else None
    if not uid:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return

    skills = app.list_user_skills(user_id=uid)
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
        InlineKeyboardButton("📂 بر اساس وضعیت", callback_data="prj_by_status")
    )
    # بازگشت‌ها
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    return kb

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_projects")
def menu_projects_cb(cq):
    """نمایش منوی پروژه‌ها (inline)"""
    cid = cq.message.chat.id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'projects_menu')
    bot.edit_message_text("پروژه‌ها:", cid, cq.message.message_id, reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "prj_list")
def prj_list_cb(cq):
    """نمایش لیست همه پروژه‌های کاربر"""
    cid = cq.message.chat.id
    show_typing(cid)
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu()); return
    rows = app.list_projects(user['id'])
    if not rows:
        bot.edit_message_text("هنوز پروژه‌ای ثبت نکرده‌اید.", cid, cq.message.message_id, reply_markup=projects_menu_markup()); return
    lines = []
    for r in rows:
        st = STATUS_FA.get(r.get('status','draft'), r.get('status','draft'))
        prg = r.get('progress', 0)
        lines.append(f"• <b>{r['title']}</b> — {st} ({prg}%)")
    bot.edit_message_text("📋 <b>لیست پروژه‌ها</b>:\n" + "\n".join(lines),
                          cid, cq.message.message_id, parse_mode="HTML", reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "prj_by_status")
def prj_by_status_cb(cq):
    """نمایش فهرست وضعیت‌ها برای فیلتر پروژه‌ها"""
    cid = cq.message.chat.id
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
    show_typing(cid)
    st = cq.data.split("::",1)[1]
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu()); return
    rows = app.projects_by_status(user['id'], st)
    if not rows:
        bot.edit_message_text(f"پروژه‌ای با وضعیت «{STATUS_FA.get(st, st)}» ندارید.",
                              cid, cq.message.message_id, reply_markup=projects_menu_markup()); return
    items = [f"• <b>{r['title']}</b> — {STATUS_FA.get(r['status'], r['status'])} ({r.get('progress',0)}%)"
             for r in rows]
    bot.edit_message_text("📂 پروژه‌ها بر اساس وضعیت:\n" + "\n".join(items),
                          cid, cq.message.message_id, parse_mode="HTML", reply_markup=projects_menu_markup())
    bot.answer_callback_query(cq.id)
@bot.callback_query_handler(func=lambda cq: cq.data == "prj_add")
def prj_add_cb(cq):
    """شروع فرآیند افزودن پروژه (مرحله عنوان)"""
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu()); return
    user_data.setdefault(cid, {})['prj'] = {}
    push_state(cid, "prj_title")
    # در مسیرهای متنی، ReplyKeyboard بازگشت/خانه را نشان بده
    bot.edit_message_text("📝 عنوان پروژه را بفرست:", cid, cq.message.message_id)
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
    """گرفتن توضیح و ثبت پروژه"""
    cid = m.chat.id
    desc = (m.text or "").strip()
    user_data[cid]['prj']['desc'] = desc
    user = app.find_user(cid)
    prj = user_data[cid]['prj']
    # ثبت پروژه (حداقل title/desc). در نسخه‌های دیگر فیلدهای بیشتری هم ممکن است اضافه شود؛ حذف نمی‌کنیم.
    prj_id = app.add_project(user['id'], prj['title'], prj['desc'])
    reset_state(cid)
    if prj_id == "DUPLICATE":
        send_and_remember(cid, "⚠️ عنوان تکراری برای همین کارفرما وجود دارد.", reply_markup=projects_menu_markup())
    elif prj_id:
        send_and_remember(cid, f"✅ پروژه «{prj['title']}» ایجاد شد.", reply_markup=projects_menu_markup())
    else:
        send_and_remember(cid, "❌ ایجاد پروژه ناموفق بود.", reply_markup=projects_menu_markup())

# =========================
# Dashboard & Reports
# =========================

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_dashboard")
def dashboard_cb(cq):
    """خلاصه داشبورد: شمارش پروژه‌ها، تفکیک وضعیت‌ها، مهارت‌ها و بودجه جمع/میانگین"""
    cid = cq.message.chat.id
    show_typing(cid)
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu()); return

    stats = app.dashboard_stats(user['id'])
    by = stats['by_status']
    bsum = stats['budget_sum'] or 0
    bavg = stats['budget_avg'] or 0

    # خلاصهٔ Top Skills (3 مورد)
    top = app.top_skills(user['id'], limit=3) or []
    top_line = "، ".join([f"{t['name']} (x{t['uses']})" for t in top]) if top else "-"

    text = (
        "📊 <b>داشبورد شما</b>\n"
        f"• پروژه‌ها: <b>{stats['projects_total']}</b>\n"
        f"   ├ باز: {by['open']} | درحال‌انجام: {by['in_progress']}\n"
        f"   └ تمام‌شده: {by['done']} | لغوشده: {by['cancelled']} | پیشنویس: {by['draft']}\n"
        f"• مهارت‌ها: <b>{stats['skills_total']}</b>\n"
        f"• بودجه: جمع {bsum} | میانگین {bavg}\n"
        f"• Top Skills: {top_line}\n"
    )

    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("باز", callback_data="dash_filter_open"),
        InlineKeyboardButton("درحال‌انجام", callback_data="dash_filter_in_progress"),
        InlineKeyboardButton("تمام‌شده", callback_data="dash_filter_done"),
    )
    kb.add(
        InlineKeyboardButton("لغوشده", callback_data="dash_filter_cancelled"),
        InlineKeyboardButton("پیشنویس", callback_data="dash_filter_draft"),
        InlineKeyboardButton("📈 گزارش بیشتر", callback_data="dash_more")
    )
    # بازگشت/خانه
    kb.add(
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"),
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
    )
    bot.edit_message_text(text, cid, cq.message.message_id, parse_mode="HTML", reply_markup=kb)
    bot.answer_callback_query(cq.id)
@bot.callback_query_handler(func=lambda cq: cq.data == "menu_switch_user")
def menu_switch_user_cb(cq):
    """نمایش ۱۰ کاربر آخرِ ثبت‌شده که telegram_id دارند، برای سوییچ تستی."""
    cid = cq.message.chat.id
    show_typing(cid)
    users = app.list_registered_users(limit=10)  # بخش B این متد را اضافه می‌کند
    if not users:
        bot.edit_message_text("فعلاً کاربری با telegram_id ثبت نشده.", cid, cq.message.message_id,
                              reply_markup=main_menu())
        bot.answer_callback_query(cq.id); return

    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        tg = u.get("telegram_id") or "-"
        name = (u.get("name") or "کاربر").strip()
        kb.add(InlineKeyboardButton(f"{name} — tg:{tg}  (#ID {u['id']})",
                                    callback_data=f"switch_to_user::{u['id']}"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu"))
    bot.edit_message_text("یک کاربر را برای ورودِ تستی انتخاب کن:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("switch_to_user::"))
def switch_to_user_cb(cq):
    """سوییچ کاربر برای همین چت (فقط درون این ربات/چت اثر دارد)."""
    cid = cq.message.chat.id
    try:
        uid = int(cq.data.split("::", 1)[1])
    except:
        bot.answer_callback_query(cq.id, "شناسه نامعتبر."); return

    session_override[cid] = uid
    if cid in logged_out:
        logged_out.discard(cid)
    bot.edit_message_text(f"✅ روی کاربر #ID {uid} سوییچ شدی.", cid, cq.message.message_id,
                          reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_logout")
def menu_logout_cb(cq):
    """خروج از حساب: از این لحظه app.find_user برای این چت، None برمی‌گرداند تا زمانی که دوباره وارد شود."""
    cid = cq.message.chat.id
    # logout = بی‌اعتباری session و بی‌اثر کردن find_user
    session_override.pop(cid, None)
    logged_out.add(cid)
    bot.edit_message_text("🚪 از حساب کاربری خارج شدی.\nبرای ورود دوباره، «🔑 ورود» یا «📋 ثبت‌نام» را بزن.",
                          cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("dash_filter_"))
def dash_filter_projects(cq):
    """فهرست پروژه‌ها بر اساس وضعیت از داشبورد"""
    cid = cq.message.chat.id
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

@bot.callback_query_handler(func=lambda cq: cq.data == "dash_more")
def dashboard_more_cb(cq):
    """گزارش تکمیلی: Top skills (۱۰تایی)، بودجهٔ انجام‌شده، آخرین پروژه‌ها"""
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.answer_callback_query(cq.id, "ابتدا وارد شوید."); return

    top = app.top_skills(user['id'], limit=10) or []
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
        InlineKeyboardButton("🏠 خانه", callback_data="back_to_menu")
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
    )

# اگر قبلاً handle_menu از 'profile' می‌خواست تابع show_profile را صدا بزند،
# این wrapper را می‌گذاریم تا با منوی جدید کار کند.
def show_profile(cq_or_msg):
    """سازگار با هر دو حالت message و callback"""
    if hasattr(cq_or_msg, "message"):   # CallbackQuery
        return menu_profile_cb(cq_or_msg)
    else:  # Message
        # در حالت پیام متنی، فقط منوی پروفایل را می‌فرستیم
        cid = cq_or_msg.chat.id
        user = app.find_user(cid)
        if not user:
            return send_and_remember(cid, "ابتدا وارد شوید", reply_markup=main_menu())
        return send_and_remember(cid, _profile_text(user), parse_mode="HTML", reply_markup=profile_menu_markup())


@bot.callback_query_handler(func=lambda cq: cq.data == "menu_profile")
def menu_profile_cb(cq):
    """نمایش پروفایل با منوی ویرایش + دکمه‌های بازگشت/خانه"""
    cid = cq.message.chat.id
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
        "phone": "شماره تلفن را بفرست:"
    }
    prompt = prompt_map.get(field, f"مقدار جدید برای {field} را بفرست:")
    # در مسیرهای متنی، ReplyKeyboard بازگشت/خانه را نشان بده
    bot.edit_message_text(f"✏️ {prompt}", cid, cq.message.message_id)
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
    # اعتبارسنجی‌های مختصر (فقط برای راهنمایی؛ منطق اصلی فایل تو حفظ می‌شود)
    if field == "hourly_rate":
        try:
            float(val)
        except:
            send_and_remember(cid, "❌ فقط عدد معتبر برای نرخ ساعتی.", reply_markup=nav_keyboard())
            return
    if field == "role" and val not in ("employer", "freelancer"):
        send_and_remember(cid, "نقش باید employer یا freelancer باشد.", reply_markup=nav_keyboard())
        return

    ok = app.update_user_profile(user['id'], field, val)
    reset_state(cid)
    if ok:
        send_and_remember(cid, "✅ ذخیره شد.", reply_markup=profile_menu_markup())
    else:
        send_and_remember(cid, "❌ خطا در ذخیره.", reply_markup=profile_menu_markup())
# =========================
# Auth: Register / Login (روتینگ به توابع موجود)
# =========================

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_register")
def menu_register_cb(cq):
    cid = cq.message.chat.id

    # اگر قبلاً حساب داری، ببین چندتاست
    users = app.list_users_by_telegram_id(cid, limit=20)
    count = app.count_users_by_telegram_id(cid)

    if count >= MAX_ACCOUNTS_PER_TELEGRAM:
        # سقف پر شده
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👤 حساب‌های من", callback_data="show_my_accounts"),
            InlineKeyboardButton("🔁 سوییچ حساب", callback_data="switch_my_account"),
        )
        bot.edit_message_text(
            f"⚠️ حداکثر {MAX_ACCOUNTS_PER_TELEGRAM} حساب می‌تونی داشته باشی و الان به سقف رسیدی.",
            cid, cq.message.message_id, reply_markup=kb
        )
        bot.answer_callback_query(cq.id); return

    if users:
        # حساب داری ولی به سقف نرسیدی → پیشنهاد نمایش / ساخت حساب جدید
        name = (users[0].get("name") or "کاربر").strip()
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("👤 حساب‌های من", callback_data="show_my_accounts"),
            InlineKeyboardButton("➕ ساخت حساب جدید", callback_data="proceed_register_new")
        )
        bot.edit_message_text(
            f"⚠️ قبلاً ثبت‌نام کردی (مثال: <b>{name}</b>)\n"
            f"می‌خوای یکی از حساب‌های قبلی رو انتخاب کنی یا یک حساب جدید بسازی؟",
            cid, cq.message.message_id, parse_mode="HTML", reply_markup=kb
        )
        bot.answer_callback_query(cq.id); return

    # اگر هیچ حسابی نبود → ثبت‌نام سریع
    gen_email = f"tg_{cid}@example.local"
    name = (cq.from_user.first_name or "کاربر") + ((" " + cq.from_user.last_name) if cq.from_user.last_name else "")
    # نقش پیشنهادی اولیه (آزاد)
    role = "freelancer"
    uid = app.add_user(telegram_id=cid, name=(name or "کاربر").strip(),
                       email=gen_email, password_hash="", role=role)
    if uid:
        try:
            session_override.pop(cid, None); logged_out.discard(cid)
        except: pass
        bot.edit_message_text("ثبت‌نام سریع انجام شد ✅", cid, cq.message.message_id, reply_markup=main_menu())
    else:
        bot.edit_message_text("❌ ثبت‌نام ناموفق بود.", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

    # 2) اگر هیچ حسابی نبود: ثبت‌نام سریع (ایمیل ساختگی + بدون پسورد)
    gen_email = f"tg_{cid}@example.local"
    name = (cq.from_user.first_name or "کاربر") + ((" " + cq.from_user.last_name) if cq.from_user.last_name else "")
    uid = app.add_user(
        telegram_id=cid,
        name=(name or "کاربر").strip(),
        email=gen_email,
        password_hash="",
        role="freelancer"
    )
    if uid:
        # اگر سیستم سوییچ/لاگ‌اوت سبک داری:
        try:
            session_override.pop(cid, None)
            logged_out.discard(cid)
        except:
            pass
        bot.edit_message_text("ثبت‌نام سریع انجام شد ✅", cid, cq.message.message_id, reply_markup=main_menu())
    else:
        bot.edit_message_text("❌ ثبت‌نام ناموفق بود.", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_login")
def menu_login_cb(cq):
    cid = cq.message.chat.id

    # اگر همین حالا واردی، دوباره نخواد
    u = app.find_user(cid)
    if u:
        name = (u.get("name") or "کاربر").strip()
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🔁 سوییچ حساب", callback_data="switch_my_account"),
            InlineKeyboardButton("👤 حساب‌های من", callback_data="show_my_accounts"),
        )
        bot.edit_message_text(f"✅ شما قبلاً وارد شده‌اید: <b>{name}</b>", cid, cq.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
        bot.answer_callback_query(cq.id); return

    # اگر وارد نیستی → اگر حساب داری، لیست حساب‌ها
    users = app.list_users_by_telegram_id(cid, limit=20)
    if users:
        bot.edit_message_text("حساب‌های شما:", cid, cq.message.message_id,
                              reply_markup=accounts_list_markup(users))
        bot.answer_callback_query(cq.id); return

    # هیچ حسابی هم نداری → ساخت حساب تست و ورود
    gen_email = f"tg_{cid}@example.local"
    name = (cq.from_user.first_name or "کاربر") + ((" " + cq.from_user.last_name) if cq.from_user.last_name else "")
    uid = app.add_user(telegram_id=cid, name=(name or "کاربر").strip(),
                       email=gen_email, password_hash="", role="freelancer")
    if uid:
        try:
            session_override.pop(cid, None); logged_out.discard(cid)
        except: pass
        bot.edit_message_text("اکانت تست ساخته شد و وارد شدی ✅", cid, cq.message.message_id, reply_markup=main_menu())
    else:
        bot.edit_message_text("❌ ورود/ساخت حساب ناموفق بود.", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

if __name__ == "__main__":
    logger.info("Bot polling started…")
    bot.polling(non_stop=True, interval=1, timeout=30, long_polling_timeout=30)


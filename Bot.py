last_bot_message_id = {}
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from Database import FreelanceBot
from CONFIG import Config
import logging, bcrypt, re, time, os
from typing import Dict, Any, List

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

logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(Config.API_TOKEN)
app = FreelanceBot()

user_steps:     Dict[int, str]            = {}
user_histories: Dict[int, List[str]]      = {}
user_data:      Dict[int, Dict[str, Any]] = {}

def send_and_remember(cid, text, **kwargs):
    if cid in last_bot_message_id:
        try:
            bot.delete_message(cid, last_bot_message_id[cid])
        except:
            pass
    msg = bot.send_message(cid, text, **kwargs)
    last_bot_message_id[cid] = msg.message_id
    return msg

def reset_state(cid: int):
    user_steps.pop(cid, None)
    user_histories.pop(cid, None)
    user_data.pop(cid, None)

def push_state(cid: int, state: str):
    h = user_histories.setdefault(cid, [])
    h.append(state)
    user_steps[cid] = state

def pop_state(cid: int) -> str:
    h = user_histories.get(cid, [])
    if h: h.pop()
    if h:
        prev = h.pop()
        user_steps[cid] = prev
        return prev
    return ''

def log_main_event(user, action, chat_id=None):
    d = {"user": user, "action": action}
    if chat_id: d["chat_id"] = chat_id
    try:
        print(d)
    except Exception: pass

def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📋 ثبت‌نام", callback_data="menu_register"),
        InlineKeyboardButton("🔑 ورود",    callback_data="menu_login"),
        InlineKeyboardButton("🛠 مهارت‌ها", callback_data="menu_skills"),
        InlineKeyboardButton("📁 پروژه‌ها", callback_data="menu_projects"),
        InlineKeyboardButton("👤 پروفایل من", callback_data="menu_profile"),
        InlineKeyboardButton("❓ راهنما",   callback_data="menu_help"),
        InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/Anakin9495")
    )
    return kb

def nav_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("🔙 بازگشت", "🏠 منوی اصلی")
    return kb
def cmd_skills(m):
    cid = m.chat.id if hasattr(m, "chat") else m.chat.id
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ افزودن", callback_data="skills_add"),
      InlineKeyboardButton("📋 لیست",   callback_data="skills_list"),
      InlineKeyboardButton("✏️ ویرایش", callback_data="skills_edit"),
      InlineKeyboardButton("🗑 حذف",    callback_data="skills_delete")
    )
    send_and_remember(cid, "مهارت‌ها:", reply_markup=kb)

def cmd_projects(m):
    cid = m.chat.id if hasattr(m, "chat") else m.chat.id
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ ثبت", callback_data="proj_add"),
      InlineKeyboardButton("📋 لیست", callback_data="proj_list"),
      InlineKeyboardButton("✏️ ویرایش", callback_data="proj_edit"),
      InlineKeyboardButton("🗑 حذف", callback_data="proj_delete")
    )
    send_and_remember(cid, "پروژه‌ها:", reply_markup=kb)

@bot.message_handler(commands=['start'])
def cmd_start(m):
    cid = m.chat.id
    reset_state(cid)
    user_histories[cid] = []
    bot.send_message(
        cid,
        f"سلام {m.from_user.first_name}!\nبرای ادامه یکی از گزینه‌ها را لمس کنید:",
        reply_markup=main_menu()
    )
    log_main_event(m.from_user.username or m.from_user.first_name, "start", chat_id=cid)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("menu_"))
def handle_menu(cq):
    cid = cq.message.chat.id
    action = cq.data.split("_",1)[1]
    log_main_event(cq.from_user.username, action, chat_id=cid)
    if   action == "register": cmd_register(cq.message)
    elif action == "login":    show_login_accounts(cq.message)
    elif action == "skills":   cmd_skills(cq.message)
    elif action == "projects": cmd_projects(cq.message)
    elif action == "help":     cmd_help(cq.message)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: m.text in ("🔙 بازگشت","🏠 منوی اصلی"))
def nav_back_home(m):
    cid, txt = m.chat.id, m.text
    if txt == "🔙 بازگشت":
        prev = pop_state(cid)
        if prev:
            resend_prompt(cid)
            return
    reset_state(cid)
    bot.send_message(cid, "🏠 منوی اصلی:", reply_markup=main_menu())

def resend_prompt(cid: int):
    prompts = {
        'await_name':            "📝 نام خود را وارد کنید:",
        'await_email':           "✉️ ایمیل خود را وارد کنید:",
        'await_pass':            "🔒 رمز عبور خود را وارد کنید:",
        'await_pass_confirm':    "🔒 تایید دوباره رمز عبور:",
        'await_role':            "🎭 نقش خود را انتخاب کنید:",
        'login_pass':            "🔒 رمز عبور را وارد کنید:",
        'add_skill_category':    "دسته‌بندی مهارت را انتخاب کنید:",
        'add_skill_name':        "نام مهارت را وارد کنید:",
        'edit_skill_select':     "یک مهارت برای ویرایش انتخاب کنید:",
        'edit_skill_category':   "دسته‌بندی جدید مهارت را انتخاب کنید:",
        'edit_skill_name':       "نام جدید مهارت را انتخاب کنید:",
        'add_proj_category':     "دسته‌بندی پروژه را انتخاب کنید:",
        'add_proj_role':         "نوع پروژه را انتخاب کنید:",
        'add_proj_title':        "عنوان پروژه را انتخاب کنید:",
        'add_proj_desc':         "توضیحات پروژه را وارد کنید:",
        'edit_proj_select':      "یک پروژه برای ویرایش انتخاب کنید:",
        'edit_proj_category':    "دسته‌بندی جدید پروژه را انتخاب کنید:",
        'edit_proj_title':       "عنوان جدید پروژه را انتخاب کنید:",
        'edit_proj_desc':        "توضیحات جدید پروژه را وارد کنید:",
    }
    bot.send_message(cid, prompts.get(user_steps.get(cid), "دوباره تلاش کنید!"), reply_markup=nav_keyboard())

def cmd_help(m):
    cid = m.chat.id
    text = (
        "راهنما:\n"
        "• ثبت‌نام و ورود فقط تایپ، سایر بخش‌ها فقط انتخاب دکمه.\n"
        "• بازگشت: مرحله قبلی. منوی اصلی: بازگشت به خانه."
    )
    bot.send_message(cid, text, reply_markup=main_menu())

# ---- ثبت‌نام ----
@bot.message_handler(commands=['register'])
def cmd_register(m):
    cid = m.chat.id
    reset_state(cid); user_histories[cid] = []; user_data[cid] = {}
    push_state(cid, 'await_name')
    send_and_remember(cid, "📝 نام خود را وارد کنید:", reply_markup=nav_keyboard())
    log_main_event(m.from_user.username, "register_start", chat_id=cid)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='await_name')
def handle_name(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    user_data[cid]['name'] = m.text.strip()
    push_state(cid, 'await_email')
    bot.send_message(cid, "✉️ ایمیل خود را وارد کنید:", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='await_email')
def handle_email(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    if not re.match(r"[^@]+@[^@]+\.[^@]+", m.text):
        bot.send_message(cid, "❌ ایمیل نامعتبر است.", reply_markup=nav_keyboard())
        return
    if app.email_exists(m.text.strip()):
        bot.send_message(cid, "❌ این ایمیل قبلاً ثبت شده است.", reply_markup=nav_keyboard())
        return
    user_data[cid]['email'] = m.text.strip()
    push_state(cid, 'await_pass')
    bot.send_message(cid, "🔒 رمز عبور خود را وارد کنید:", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='await_pass')
def handle_pass(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    pwd = m.text.strip()
    user_data[cid]['pwd'] = pwd
    push_state(cid, 'await_pass_confirm')
    bot.send_message(cid, "🔒 تایید دوباره رمز عبور:", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='await_pass_confirm')
def handle_pass_confirm(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    pwd_confirm = m.text.strip()
    if pwd_confirm != user_data[cid]['pwd']:
        bot.send_message(cid, "❌ رمزها یکسان نیستند. دوباره امتحان کنید.", reply_markup=nav_keyboard())
        push_state(cid, 'await_pass')
        bot.send_message(cid, "🔒 رمز عبور خود را وارد کنید:", reply_markup=nav_keyboard())
        return
    user_data[cid]['pwd_hash'] = bcrypt.hashpw(user_data[cid]['pwd'].encode(), bcrypt.gensalt()).decode()
    push_state(cid, 'await_role')
    kb = InlineKeyboardMarkup(row_width=2)
    for i, role in enumerate(ROLES):
        kb.add(InlineKeyboardButton(role, callback_data=f"role_{i}"))
    bot.send_message(cid, "🎭 نقش خود را انتخاب کنید:", reply_markup=kb)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("role_"))
def handle_role_cb(cq):
    cid = cq.message.chat.id
    idx = int(cq.data.split("_")[1])
    role = ROLES[idx]
    data = user_data[cid]
    uid = app.add_user(cid, data['name'], data['email'], data['pwd_hash'], role)
    if uid:
        bot.edit_message_text(f"✅ ثبت‌نام انجام شد! شناسه شما: {uid}", cid, cq.message.message_id, reply_markup=main_menu())
        log_main_event(cq.from_user.username, "register_success", chat_id=cid)
    else:
        bot.edit_message_text("❌ خطا در ثبت‌نام. دوباره تلاش کنید.", cid, cq.message.message_id, reply_markup=main_menu())
    reset_state(cid)
    bot.answer_callback_query(cq.id)

# ---- ورود با لیست حساب ----
def show_login_accounts(m):
    cid = m.chat.id
    reset_state(cid); user_histories[cid] = []
    accounts = app.list_my_accounts(cid)
    if not accounts:
        bot.send_message(cid, "هیچ حسابی برای این شماره ثبت نشده! لطفاً ثبت‌نام کنید.", reply_markup=main_menu())
        cmd_register(m)
        return
    kb = InlineKeyboardMarkup()
    for acc in accounts:
        kb.add(InlineKeyboardButton(
            f"{acc['name']} ({acc['email']})",
            callback_data=f"login_acc_{acc['id']}"
        ))
    kb.add(InlineKeyboardButton("ثبت‌نام جدید", callback_data="menu_register"))
    bot.send_message(cid, "یکی از حساب‌های ثبت‌شده خود را انتخاب کنید:", reply_markup=kb)
    push_state(cid, 'choose_account')

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("login_acc_"))
def handle_login_account(cq):
    cid = cq.message.chat.id
    user_id = int(cq.data.split("_")[2])
    user_data.setdefault(cid, {})['login_user_id'] = user_id
    push_state(cid, 'login_pass')
    bot.edit_message_text("🔒 رمز عبور خود را وارد کنید:", cid, cq.message.message_id)
    log_main_event(cq.from_user.username, "login_password_input", chat_id=cid)
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='login_pass')
def login_pass(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    pwd = m.text.strip()
    user_id = user_data[cid]['login_user_id']
    user = app.get_user_by_id(user_id)
    if not user or not bcrypt.checkpw(pwd.encode(), user['password_hash'].encode()):
        bot.send_message(cid, "❌ ایمیل یا رمز اشتباه است.", reply_markup=main_menu())
        reset_state(cid)
    else:
        bot.send_message(cid, f"👋 خوش آمدید {user['name']}!", reply_markup=main_menu())
        log_main_event(user['email'], "login_success", chat_id=cid)
        reset_state(cid)

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_skills")
def _skills_cb(cq):
    cid = cq.message.chat.id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'skills_menu')
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ افزودن", callback_data="skills_add"),
      InlineKeyboardButton("📋 لیست",   callback_data="skills_list"),
      InlineKeyboardButton("✏️ ویرایش", callback_data="skills_edit"),
      InlineKeyboardButton("🗑 حذف",    callback_data="skills_delete")
    )
    bot.edit_message_text("مهارت‌ها:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_add")
def skills_add_cb(cq):
    cid = cq.message.chat.id
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"skillcat_{idx}") for idx, cat in enumerate(SKILL_CATEGORIES)]
    for i in range(0, len(buttons), 2):
        kb.add(*buttons[i:i+2])
    bot.edit_message_text("دسته‌بندی مهارت را انتخاب کنید:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "skills_list")
def skills_list_cb(cq):
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    # لیست مهارت‌ها با join جدول user_skill و skill
    skills = app.list_user_skills(user['id'])
    if not skills:
        bot.edit_message_text("🔹 شما هنوز هیچ مهارتی ثبت نکرده‌اید!", cid, cq.message.message_id, reply_markup=main_menu())
    else:
        msg = "🛠 <b>لیست مهارت‌های شما:</b>\n" + "\n".join(
            [f"{idx+1}. {sk['name']} ({sk['category']})" for idx, sk in enumerate(skills)]
        )
        bot.edit_message_text(msg, cid, cq.message.message_id, parse_mode="HTML", reply_markup=main_menu())
    bot.answer_callback_query(cq.id)


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("skillcat_"))
def skill_category_selected_cb(cq):
    cid = cq.message.chat.id
    idx = int(cq.data.split("_")[1])
    user_data.setdefault(cid, {})['skill_category'] = SKILL_CATEGORIES[idx]
    push_state(cid, 'add_skill_name')
    send_and_remember(cid, "نام مهارت را وارد کنید:", reply_markup=nav_keyboard())
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='add_skill_name')
def handle_add_skill_name(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    name = m.text.strip()
    user_data.setdefault(cid, {})['skill_name'] = name
    user = app.find_user(cid)
    skill_id = app.add_skill(name, user_data[cid]['skill_category'])
    if skill_id:
        app.add_user_skill(user['id'], skill_id)
        send_and_remember(cid, "✅ مهارت ثبت شد!", reply_markup=main_menu())
        log_main_event(user['email'], "skill_add_success", chat_id=cid)
    else:
        send_and_remember(cid, "❌ خطا در ثبت مهارت.", reply_markup=main_menu())
    reset_state(cid)
    if skill_id == "DUPLICATE":
        send_and_remember(cid, "❌ این مهارت قبلاً ثبت شده است! لطفاً مهارت جدید وارد کنید.", reply_markup=main_menu())
    elif not skill_id:
        send_and_remember(cid, "❌ خطا در ثبت مهارت. داده‌ها را بررسی کنید.", reply_markup=main_menu())
    else:
        send_and_remember(cid, "✅ مهارت ثبت شد!", reply_markup=main_menu())
    reset_state(cid)

# (به همین سبک برای ویرایش و حذف هم باید edit_message_text و دکمه‌ها رعایت شود)

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_projects")
def _proj_cb(cq):
    cid = cq.message.chat.id
    reset_state(cid); user_histories[cid] = []
    push_state(cid, 'projects_menu')
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ ثبت", callback_data="proj_add"),
      InlineKeyboardButton("📋 لیست", callback_data="proj_list"),
      InlineKeyboardButton("✏️ ویرایش", callback_data="proj_edit"),
      InlineKeyboardButton("🗑 حذف", callback_data="proj_delete")
    )
    bot.edit_message_text("پروژه‌ها:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "proj_add")
def proj_add_cb(cq):
    cid = cq.message.chat.id
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"projcat_{idx}") for idx, cat in enumerate(PROJECT_CATEGORIES)]
    for i in range(0, len(buttons), 2):
        kb.add(*buttons[i:i+2])
    bot.edit_message_text("دسته‌بندی پروژه را انتخاب کنید:", cid, cq.message.message_id, reply_markup=kb)
    bot.answer_callback_query(cq.id)


@bot.callback_query_handler(func=lambda cq: cq.data.startswith("projcat_"))
def proj_category_selected_cb(cq):
    cid = cq.message.chat.id
    idx = int(cq.data.split("_")[1])
    user_data.setdefault(cid, {})['proj_category'] = PROJECT_CATEGORIES[idx]
    push_state(cid, 'add_proj_role')
    kb = InlineKeyboardMarkup(row_width=2)
    for i, role in enumerate(ROLES):
        kb.add(InlineKeyboardButton(role, callback_data=f"projrole_{i}"))
    bot.send_message(cid, "نوع پروژه (کارفرما یا کارمند) را انتخاب کنید:", reply_markup=kb)
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("projrole_"))
def proj_role_selected_cb(cq):
    cid = cq.message.chat.id
    idx = int(cq.data.split("_")[1])
    user_data.setdefault(cid, {})['proj_role'] = ROLES[idx]
    push_state(cid, 'add_proj_info')
    text = (
        "لطفاً اطلاعات پروژه را با قالب زیر و در یک پیام وارد کنید:\n\n"
        "<b>عنوان پروژه:</b> طراحی سایت\n"
        "<b>توضیحات پروژه:</b> فروشگاه آنلاین با درگاه پرداخت\n"
        "<b>بودجه (تومان):</b> 8000000\n"
        "<b>زمان تحویل (روز):</b> 14\n\n"
        "هر مورد را در یک خط جداگانه و مانند مثال بالا وارد کنید."
    )
    send_and_remember(cid, text, parse_mode="HTML", reply_markup=nav_keyboard())
    bot.answer_callback_query(cq.id)


@bot.callback_query_handler(func=lambda cq: cq.data == "proj_list")
def proj_list_cb(cq):
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("ابتدا وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    projects = app.list_projects(user['id'])
    if not projects:
        bot.edit_message_text("🔹 شما هنوز هیچ پروژه‌ای ثبت نکرده‌اید!", cid, cq.message.message_id, reply_markup=main_menu())
    else:
        msg = "📁 <b>لیست پروژه‌های شما:</b>\n" + "\n".join(
            [f"{idx+1}. {pr['title']}" for idx, pr in enumerate(projects)]
        )
        bot.edit_message_text(msg, cid, cq.message.message_id, parse_mode="HTML", reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='add_proj_title')
def handle_add_proj_title(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    user_data.setdefault(cid, {})['proj_title'] = m.text.strip()
    push_state(cid, 'add_proj_desc')
    bot.send_message(cid, "توضیحات پروژه را وارد کنید:", reply_markup=nav_keyboard())

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='add_proj_desc')
def handle_add_proj_desc(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    desc = m.text.strip()
    user = app.find_user(cid)
    data = user_data[cid]
    pid = app.add_project(
        user['id'],
        data['proj_title'],
        desc,
        data.get('proj_category'),
        data.get('proj_role')
    )
    bot.send_message(cid, f"✅ پروژه ثبت شد! ID: {pid}" if pid else "❌ خطا در ثبت پروژه.", reply_markup=main_menu())
    log_main_event(user['email'], "project_add_success", chat_id=cid)
    reset_state(cid)
    if pid == "DUPLICATE":
        bot.send_message(cid, "❌ پروژه‌ای با این عنوان قبلاً ثبت کرده‌اید!\nلطفاً عنوان جدید وارد کنید.",
                         reply_markup=main_menu())
    elif not pid:
        bot.send_message(cid, "❌ خطا در ثبت پروژه. لطفاً همه فیلدها را چک کنید.", reply_markup=main_menu())
    else:
        bot.send_message(cid, f"✅ پروژه ثبت شد! ID: {pid}", reply_markup=main_menu())
    reset_state(cid)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id)=='add_proj_info')
def handle_add_proj_info(m):
    if m.text in ("🔙 بازگشت","🏠 منوی اصلی"): return
    cid = m.chat.id
    lines = m.text.strip().split("\n")
    if len(lines) < 4:
        bot.send_message(cid, "❌ لطفاً همه بخش‌ها را کامل و هر مورد را در یک خط جدا وارد کنید.", reply_markup=nav_keyboard())
        return
    try:
        title = lines[0].replace("عنوان پروژه:", "").strip()
        desc = lines[1].replace("توضیحات پروژه:", "").strip()
        budget = int(lines[2].replace("بودجه (تومان):", "").replace("تومان", "").strip())
        delivery = int(lines[3].replace("زمان تحویل (روز):", "").replace("روز", "").strip())
    except Exception:
        bot.send_message(cid, "❌ خطا در خواندن اطلاعات! قالب را دقیق رعایت کن.", reply_markup=nav_keyboard())
        return
    user = app.find_user(cid)
    proj_id = app.add_project(
        user['id'],
        title,
        desc,
        user_data[cid].get('proj_category'),
        user_data[cid].get('proj_role')

    )
    if proj_id == "DUPLICATE":
        bot.send_message(cid, "❌ پروژه‌ای با این عنوان قبلاً ثبت کرده‌اید!\nلطفاً عنوان جدید وارد کنید.", reply_markup=main_menu())
    elif not proj_id:
        bot.send_message(cid, "❌ خطا در ثبت پروژه. لطفاً همه فیلدها را چک کنید.", reply_markup=main_menu())
    else:
        bot.send_message(cid, f"✅ پروژه ثبت شد! ID: {proj_id}", reply_markup=main_menu())
    reset_state(cid)

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == 'add_proj_delivery')
def handle_add_proj_delivery(m):
    cid = m.chat.id
    try:
        delivery = int(m.text.strip())
        if delivery < 1:
            raise ValueError()
        user_data[cid]['proj_delivery'] = delivery
    except:
        send_and_remember(cid, "❌ مدت زمان باید عدد صحیح (روز) و حداقل ۱ روز باشد.", reply_markup=nav_keyboard())
        return

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == 'add_proj_budget')
def handle_add_proj_budget(m):
    cid = m.chat.id
    try:
        budget = int(m.text.strip())
        if budget < 10000:
            raise ValueError()
        user_data[cid]['proj_budget'] = budget      # <<<<<< اضافه کن
    except:
        send_and_remember(cid, "❌ بودجه باید یک عدد صحیح و بیشتر از ۱۰ هزار تومان باشد.", reply_markup=nav_keyboard())
        return
    push_state(cid, 'add_proj_delivery')
    send_and_remember(cid, "مدت زمان انجام پروژه (روز):", reply_markup=nav_keyboard())

@bot.callback_query_handler(func=lambda cq: cq.data == "menu_profile")
def show_profile(cq):
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("کاربر یافت نشد! لطفاً وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    prof = app.get_user_profile(user['id'])
    text = (
        f"👤 <b>پروفایل کاربر</b>\n"
        f"نام: {prof.get('name','')}\n"
        f"ایمیل: {prof.get('email','')}\n"
        f"نقش: {prof.get('role','')}\n"
        f"بیوگرافی: {prof.get('bio','-')}\n"
        f"شماره تماس: {prof.get('phone','-')}\n"
        f"لینکدین: {prof.get('linkedin','-')}\n"
        f"گیتهـاب: {prof.get('github','-')}\n"
        f"امتیاز: {prof.get('rating', '-')}\n"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ ویرایش بیو", callback_data="editprofile_bio"),
        InlineKeyboardButton("✏️ ویرایش شماره", callback_data="editprofile_phone"),
        InlineKeyboardButton("✏️ ویرایش لینکدین", callback_data="editprofile_linkedin"),
        InlineKeyboardButton("✏️ ویرایش گیتهاب", callback_data="editprofile_github"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")
    )
    bot.edit_message_text(text, cid, cq.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "back_to_menu")
def back_to_menu_cb(cq):
    cid = cq.message.chat.id
    bot.edit_message_text("🏠 منوی اصلی:", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("editprofile_"))
def profile_edit_start(cq):
    cid = cq.message.chat.id
    field = cq.data.split("_",1)[1]
    fields_fa = {
        "bio": "بیوگرافی",
        "phone": "شماره تماس",
        "linkedin": "آدرس لینکدین",
        "github": "آدرس گیتهاب"
    }
    user_data.setdefault(cid, {})["editprofile_field"] = field
    bot.send_message(cid, f"لطفاً {fields_fa[field]} جدید را وارد کنید:", reply_markup=nav_keyboard())
    bot.answer_callback_query(cq.id)
    push_state(cid, 'editprofile_wait')

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == 'editprofile_wait')
def profile_edit_save(m):
    cid = m.chat.id
    field = user_data[cid]["editprofile_field"]
    user = app.find_user(cid)
    app.update_user_profile(user['id'], field, m.text.strip())
    bot.send_message(cid, "✅ ذخیره شد!", reply_markup=main_menu())
    reset_state(cid)
@bot.callback_query_handler(func=lambda cq: cq.data == "menu_profile")
def show_profile(cq):
    cid = cq.message.chat.id
    user = app.find_user(cid)
    if not user:
        bot.edit_message_text("کاربر یافت نشد! لطفاً وارد شوید.", cid, cq.message.message_id, reply_markup=main_menu())
        return
    prof = app.get_user_profile(user['id'])
    text = (
        f"👤 <b>پروفایل کاربر</b>\n"
        f"نام: {prof.get('name','')}\n"
        f"ایمیل: {prof.get('email','')}\n"
        f"نقش: {prof.get('role','')}\n"
        f"بیوگرافی: {prof.get('bio','-')}\n"
        f"شماره تماس: {prof.get('phone','-')}\n"
        f"لینکدین: {prof.get('linkedin','-')}\n"
        f"گیتهاب: {prof.get('github','-')}\n"
        f"وب‌سایت: {prof.get('website','-')}\n"
        f"دستمزد ساعتی: {prof.get('hourly_rate','-')}\n"
        f"امتیاز: {prof.get('rating', '-')}\n"
        f"عکس پروفایل: {prof.get('profile_picture','-')}\n"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ ویرایش نام", callback_data="editprofile_name"),
        InlineKeyboardButton("✏️ ویرایش بیو", callback_data="editprofile_bio"),
        InlineKeyboardButton("✏️ ویرایش شماره", callback_data="editprofile_phone"),
        InlineKeyboardButton("✏️ ویرایش لینکدین", callback_data="editprofile_linkedin"),
        InlineKeyboardButton("✏️ ویرایش گیتهاب", callback_data="editprofile_github"),
        InlineKeyboardButton("✏️ ویرایش وب‌سایت", callback_data="editprofile_website"),
        InlineKeyboardButton("✏️ ویرایش دستمزد", callback_data="editprofile_hourly_rate"),
        InlineKeyboardButton("✏️ ویرایش عکس پروفایل", callback_data="editprofile_profile_picture"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_menu")
    )
    bot.edit_message_text(text, cid, cq.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data == "back_to_menu")
def back_to_menu_cb(cq):
    cid = cq.message.chat.id
    bot.edit_message_text("🏠 منوی اصلی:", cid, cq.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(cq.id)

@bot.callback_query_handler(func=lambda cq: cq.data.startswith("editprofile_"))
def profile_edit_start(cq):
    cid = cq.message.chat.id
    field = cq.data.split("_",1)[1]
    fields_fa = {
        "name": "نام",
        "bio": "بیوگرافی",
        "phone": "شماره تماس",
        "linkedin": "آدرس لینکدین",
        "github": "آدرس گیتهاب",
        "website": "وب‌سایت",
        "hourly_rate": "دستمزد ساعتی",
        "profile_picture": "آدرس عکس پروفایل (URL عکس)"
    }
    user_data.setdefault(cid, {})["editprofile_field"] = field
    bot.send_message(cid, f"لطفاً {fields_fa[field]} جدید را وارد کنید:", reply_markup=nav_keyboard())
    bot.answer_callback_query(cq.id)
    push_state(cid, 'editprofile_wait')

@bot.message_handler(func=lambda m: user_steps.get(m.chat.id) == 'editprofile_wait')
def profile_edit_save(m):
    cid = m.chat.id
    field = user_data[cid]["editprofile_field"]
    user = app.find_user(cid)
    app.update_user_profile(user['id'], field, m.text.strip())
    bot.send_message(cid, "✅ ذخیره شد!", reply_markup=main_menu())
    reset_state(cid)

if __name__ == "__main__":
    print(f"[CMD] Starting: {os.path.abspath(__file__)}")
    while True:
        try:
            bot.polling(non_stop=True, timeout=5)
        except Exception as e:
            logger.critical(f"Polling crashed: {e}", exc_info=True)
            time.sleep(5)

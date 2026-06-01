"""
Andijon FC Fan Challenge Bot
============================
Bitta fayl — to'liq bot.
Stack: aiogram 3.x · aiosqlite · Redis (ixtiyoriy) · APScheduler · Railway/Render
"""

import asyncio, hashlib, logging, os, random, time
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, Update
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import aiosqlite

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "andijon_fc_secret")
WEBHOOK_HOST   = os.getenv("WEBHOOK_HOST", "")          # https://yourapp.railway.app
WEBHOOK_PATH   = "/webhook"
WEBAPP_HOST    = "0.0.0.0"
WEBAPP_PORT    = int(os.getenv("PORT", 8080))

MAIN_CHANNEL   = os.getenv("MAIN_CHANNEL", "@AndijonFC")      # asosiy kanal
EXTRA_CHANNELS = os.getenv("EXTRA_CHANNELS", "").split(",")   # qo'shimcha kanallar (vergul bilan)
ADMIN_IDS      = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH        = "bot.db"

CAMPAIGN_DAYS  = 3        # kampaniya davomiyligi
MIN_BALLS_GIVEAWAY = 50   # g'oyibona uchun minimal ball

# Ball miqdorlari
BALLS = {
    "quiz_correct":   20,
    "quiz_wrong":      0,
    "post_reaction":  10,
    "referral":       30,
    "image_task":     15,
    "flash_correct":  25,
    "streak_bonus":   10,   # 3+ kun ketma-ket bonus
}

# Fan Passport darajalari: (nomi, emoji, min_ball)
FAN_LEVELS = [
    (1000, "👑", "Super Fan"),
    (600,  "🥇", "Oltin muxlis"),
    (300,  "🥈", "Kumush muxlis"),
    (100,  "🥉", "Bronza muxlis"),
    (0,    "⚽", "Yangi muxlis"),
]

# Vazifa nishonlari
TASK_BADGES = {
    "first_quiz":   ("🎯", "Birinchi viktorina"),
    "streak_3":     ("🔥", "3 kunlik seria"),
    "referral_5":   ("🤝", "5 do'st taklif"),
    "top_10":       ("🏆", "TOP 10"),
    "speed_demon":  ("⚡", "Tezkor javob ustasi"),
}


# ─────────────────────────────────────────────
# DATABASE  (aiosqlite — bitta fayl, deploy-ga qulay)
# ─────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY,
            tg_id        INTEGER UNIQUE NOT NULL,
            name         TEXT,
            username     TEXT,
            balls        INTEGER DEFAULT 0,
            streak       INTEGER DEFAULT 0,
            last_active  TEXT,
            fan_level    TEXT DEFAULT 'Yangi muxlis',
            badges       TEXT DEFAULT '',
            joined_at    TEXT DEFAULT (datetime('now')),
            is_banned    INTEGER DEFAULT 0,
            ref_by       INTEGER
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id      INTEGER NOT NULL,
            task_type  TEXT NOT NULL,          -- quiz / reaction / referral / image / flash
            task_date  TEXT NOT NULL,
            balls      INTEGER DEFAULT 0,
            done_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(tg_id, task_type, task_date)
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT NOT NULL,
            opt_a       TEXT, opt_b TEXT, opt_c TEXT, opt_d TEXT,
            answer      TEXT NOT NULL,           -- 'a','b','c','d'
            is_flash    INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS flash_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id    INTEGER NOT NULL,
            opened_at  TEXT NOT NULL,
            closed_at  TEXT,
            active     INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS giveaway_winners (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id      INTEGER NOT NULL,
            balls      INTEGER,
            tickets    INTEGER,
            total_pool INTEGER,
            won_at     TEXT DEFAULT (datetime('now'))
        );
        """)
        await db.commit()


async def db_get(sql: str, params=()) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_all(sql: str, params=()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_run(sql: str, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(sql, params)
        await db.commit()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_fan_level(balls: int) -> tuple[str, str]:
    for min_b, emoji, name in FAN_LEVELS:
        if balls >= min_b:
            return emoji, name
    return "⚽", "Yangi muxlis"

async def add_balls(tg_id: int, amount: int, task_type: str) -> int:
    """Ball qo'shadi, daraja yangilaydi, badge tekshiradi."""
    await db_run(
        "UPDATE users SET balls = balls + ?, last_active = ? WHERE tg_id = ?",
        (amount, today(), tg_id)
    )
    # Task log (UNIQUE — kuniga bir marta)
    try:
        await db_run(
            "INSERT INTO tasks (tg_id, task_type, task_date, balls) VALUES (?,?,?,?)",
            (tg_id, task_type, today(), amount)
        )
    except Exception:
        pass  # allaqachon bajarilgan

    user = await db_get("SELECT balls FROM users WHERE tg_id=?", (tg_id,))
    total = user["balls"] if user else 0
    _, level_name = get_fan_level(total)
    await db_run("UPDATE users SET fan_level=? WHERE tg_id=?", (level_name, tg_id))
    return total

async def task_done_today(tg_id: int, task_type: str) -> bool:
    row = await db_get(
        "SELECT id FROM tasks WHERE tg_id=? AND task_type=? AND task_date=?",
        (tg_id, task_type, today())
    )
    return row is not None

async def get_or_create_user(msg: Message, ref_id: Optional[int] = None):
    user = await db_get("SELECT * FROM users WHERE tg_id=?", (msg.from_user.id,))
    if not user:
        name = msg.from_user.full_name
        await db_run(
            "INSERT INTO users (tg_id, name, username, ref_by) VALUES (?,?,?,?)",
            (msg.from_user.id, name, msg.from_user.username, ref_id)
        )
        # Referral bonusi
        if ref_id and ref_id != msg.from_user.id:
            await add_balls(ref_id, BALLS["referral"], "referral")
            ref_count = await db_get(
                "SELECT COUNT(*) as cnt FROM users WHERE ref_by=?", (ref_id,)
            )
            if ref_count and ref_count["cnt"] == 5:
                await award_badge(ref_id, "referral_5")
    return await db_get("SELECT * FROM users WHERE tg_id=?", (msg.from_user.id,))

async def award_badge(tg_id: int, badge_key: str) -> Optional[str]:
    user = await db_get("SELECT badges FROM users WHERE tg_id=?", (tg_id,))
    if not user:
        return None
    badges = user["badges"].split(",") if user["badges"] else []
    if badge_key not in badges:
        badges.append(badge_key)
        await db_run(
            "UPDATE users SET badges=? WHERE tg_id=?",
            (",".join(filter(None, badges)), tg_id)
        )
        emoji, name = TASK_BADGES.get(badge_key, ("🎖", badge_key))
        return f"{emoji} Yangi badge: <b>{name}</b>"
    return None

async def check_subscriptions(bot: Bot, tg_id: int) -> bool:
    channels = [MAIN_CHANNEL] + [c for c in EXTRA_CHANNELS if c.strip()]
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, tg_id)
            if member.status in ("left", "kicked", "restricted"):
                return False
        except Exception:
            pass
    return True

def anti_cheat_check(tg_id: int) -> bool:
    """Telegram ID orqali account yoshini taxmin qiladi."""
    # ~7 mlrd dan katta ID = juda yangi (2023+)
    if tg_id > 6_000_000_000:
        return False
    return True

def kb(*rows: list) -> InlineKeyboardMarkup:
    """Inline keyboard qulay builder."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**btn) for btn in row]
        for row in rows
    ])


# ─────────────────────────────────────────────
# KEYBOARDS (qayta ishlatiladigan)
# ─────────────────────────────────────────────
def main_menu_kb():
    return kb(
        [{"text": "🎯 Viktorina",    "callback_data": "quiz"},
         {"text": "📋 Vazifalar",    "callback_data": "tasks"}],
        [{"text": "🏆 Reyting",      "callback_data": "leaderboard"},
         {"text": "👤 Profilim",     "callback_data": "profile"}],
        [{"text": "🔗 Do'st taklif", "callback_data": "referral"}],
    )

def sub_check_kb(channels: list) -> InlineKeyboardMarkup:
    rows = [[{"text": f"📢 {ch}", "url": f"https://t.me/{ch.lstrip('@')}"}] for ch in channels]
    rows.append([{"text": "✅ Tekshirish", "callback_data": "check_sub"}])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────
router = Router()


# ── /start ───────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message, bot: Bot):
    # Anti-cheat
    if not anti_cheat_check(msg.from_user.id):
        await msg.answer("⛔ Kechirasiz, yangi akkauntlar qatnasha olmaydi.")
        return

    # Referral ID ajratish
    ref_id = None
    args = msg.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])

    await get_or_create_user(msg, ref_id)

    # Obuna tekshirish
    if not await check_subscriptions(bot, msg.from_user.id):
        channels = [MAIN_CHANNEL] + [c for c in EXTRA_CHANNELS if c.strip()]
        await msg.answer(
            "🏆 <b>Andijon FC Fan Challenge</b>\n\n"
            "Qatnashish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=sub_check_kb(channels),
            parse_mode="HTML"
        )
        return

    await msg.answer(
        f"⚽ Salom, <b>{msg.from_user.first_name}</b>!\n\n"
        "🏆 <b>Andijon FC Fan Challenge</b>ga xush kelibsiz!\n\n"
        "3 kun davomida ball to'plang va sovrinni qo'lga kiriting:\n"
        "🎁 Futbolchi imzosi tushirilgan futbolka\n"
        "🎁 VIP stadion chiptasi\n"
        "🎁 Klub merchi\n\n"
        "Quyidagi menyu orqali boshlang 👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: CallbackQuery, bot: Bot):
    if not await check_subscriptions(bot, cb.from_user.id):
        await cb.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
        return
    await cb.message.edit_text(
        f"✅ Zo'r! Salom, <b>{cb.from_user.first_name}</b>!\n\n"
        "Menyudan boshlang 👇",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )


# ── PROFILE ──────────────────────────────────
@router.callback_query(F.data == "profile")
async def show_profile(cb: CallbackQuery):
    user = await db_get("SELECT * FROM users WHERE tg_id=?", (cb.from_user.id,))
    if not user:
        await cb.answer("Avval /start bosing")
        return

    emoji, level = get_fan_level(user["balls"])
    badges_raw = user["badges"].split(",") if user["badges"] else []
    badge_icons = "".join(
        TASK_BADGES[b][0] for b in badges_raw if b in TASK_BADGES
    ) or "—"

    # Reyting
    rank_row = await db_get(
        "SELECT COUNT(*)+1 AS rank FROM users WHERE balls > ? AND is_banned=0",
        (user["balls"],)
    )
    rank = rank_row["rank"] if rank_row else "?"

    ref_count = await db_get(
        "SELECT COUNT(*) AS cnt FROM users WHERE ref_by=?", (cb.from_user.id,)
    )

    await cb.message.edit_text(
        f"👤 <b>Profil</b>\n\n"
        f"Ism: {user['name']}\n"
        f"Daraja: {emoji} <b>{level}</b>\n"
        f"🏅 Ball: <b>{user['balls']}</b>\n"
        f"📊 Reyting: <b>#{rank}</b>\n"
        f"🔗 Taklif qilganlar: <b>{ref_count['cnt'] if ref_count else 0}</b>\n"
        f"🎖 Nishonlar: {badge_icons}\n"
        f"🔥 Seria: {user['streak']} kun",
        reply_markup=kb([{"text": "⬅️ Orqaga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


# ── LEADERBOARD ───────────────────────────────
@router.callback_query(F.data == "leaderboard")
async def show_leaderboard(cb: CallbackQuery):
    top = await db_all(
        "SELECT tg_id, name, balls FROM users WHERE is_banned=0 ORDER BY balls DESC LIMIT 10"
    )
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>TOP 10 MUXLISLAR</b>\n\n"
    for i, u in enumerate(top):
        m = medals[i] if i < 3 else f"{i+1}."
        marker = " ◀️" if u["tg_id"] == cb.from_user.id else ""
        text += f"{m} {u['name'] or 'Foydalanuvchi'} — <b>{u['balls']}</b> ball{marker}\n"

    me = await db_get("SELECT balls FROM users WHERE tg_id=?", (cb.from_user.id,))
    if me:
        rank = await db_get(
            "SELECT COUNT(*)+1 AS r FROM users WHERE balls>? AND is_banned=0",
            (me["balls"],)
        )
        text += f"\n📍 Sizning o'rningiz: <b>#{rank['r']}</b> ({me['balls']} ball)"

    await cb.message.edit_text(
        text,
        reply_markup=kb([{"text": "⬅️ Orqaga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


# ── VAZIFALAR HUB ─────────────────────────────
@router.callback_query(F.data == "tasks")
async def show_tasks(cb: CallbackQuery):
    done_quiz     = await task_done_today(cb.from_user.id, "quiz")
    done_reaction = await task_done_today(cb.from_user.id, "reaction")
    done_image    = await task_done_today(cb.from_user.id, "image_task")

    def status(done): return "✅" if done else "⭕"

    await cb.message.edit_text(
        "📋 <b>Bugungi vazifalar</b>\n\n"
        f"{status(done_quiz)}  Kunlik viktorina — <b>+{BALLS['quiz_correct']}</b> ball\n"
        f"{status(done_reaction)}  Post reaksiyasi — <b>+{BALLS['post_reaction']}</b> ball\n"
        f"{status(done_image)}  Futbolchini toping — <b>+{BALLS['image_task']}</b> ball\n"
        f"⭕  Tezkor savol (19:00) — <b>+{BALLS['flash_correct']}</b> ball\n\n"
        "🔗 Do'st taklif — <b>+30</b> ball (har biri uchun)",
        reply_markup=kb(
            [{"text": "🎯 Viktorina",       "callback_data": "quiz"},
             {"text": "❤️ Reaksiya",         "callback_data": "reaction_task"}],
            [{"text": "🔍 Futbolchini top",  "callback_data": "image_task"}],
            [{"text": "⬅️ Orqaga",           "callback_data": "back_main"}],
        ),
        parse_mode="HTML"
    )


# ── QUIZ ──────────────────────────────────────
@router.callback_query(F.data == "quiz")
async def show_quiz(cb: CallbackQuery):
    if await task_done_today(cb.from_user.id, "quiz"):
        await cb.answer("✅ Bugun viktorinani allaqachon bajardingiz!", show_alert=True)
        return

    quiz = await db_get(
        "SELECT * FROM quizzes WHERE is_flash=0 AND active=1 ORDER BY RANDOM() LIMIT 1"
    )
    if not quiz:
        await cb.answer("Hozircha savol yo'q. Keyinroq urinib ko'ring.", show_alert=True)
        return

    opts = [
        (f"A) {quiz['opt_a']}", f"qa_{quiz['id']}_a"),
        (f"B) {quiz['opt_b']}", f"qa_{quiz['id']}_b"),
        (f"C) {quiz['opt_c']}", f"qa_{quiz['id']}_c"),
        (f"D) {quiz['opt_d']}", f"qa_{quiz['id']}_d"),
    ]
    await cb.message.edit_text(
        f"🎯 <b>Savol:</b>\n\n{quiz['question']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=d)] for t, d in opts
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("qa_"))
async def quiz_answer(cb: CallbackQuery, bot: Bot):
    if await task_done_today(cb.from_user.id, "quiz"):
        await cb.answer("Allaqachon javob berdingiz!", show_alert=True)
        return

    _, quiz_id, chosen = cb.data.split("_")
    quiz = await db_get("SELECT * FROM quizzes WHERE id=?", (quiz_id,))
    if not quiz:
        return

    is_correct = chosen == quiz["answer"]
    if is_correct:
        total = await add_balls(cb.from_user.id, BALLS["quiz_correct"], "quiz")
        # Birinchi quiz badge
        badge_msg = await award_badge(cb.from_user.id, "first_quiz")
        text = (
            f"✅ <b>To'g'ri!</b> +{BALLS['quiz_correct']} ball\n"
            f"💰 Jami ball: <b>{total}</b>"
        )
        if badge_msg:
            text += f"\n\n{badge_msg}"
    else:
        correct_text = quiz[f"opt_{quiz['answer']}"]
        text = f"❌ <b>Noto'g'ri.</b>\nTo'g'ri javob: <b>{correct_text}</b>"
        # Noto'g'ri ham log sifatida yozish (qayta bosmaslik uchun)
        try:
            await db_run(
                "INSERT INTO tasks (tg_id, task_type, task_date, balls) VALUES (?,?,?,?)",
                (cb.from_user.id, "quiz", today(), 0)
            )
        except Exception:
            pass

    await cb.message.edit_text(
        text,
        reply_markup=kb([{"text": "⬅️ Menyuga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


# ── REACTION TASK ─────────────────────────────
@router.callback_query(F.data == "reaction_task")
async def reaction_task(cb: CallbackQuery):
    if await task_done_today(cb.from_user.id, "reaction"):
        await cb.answer("✅ Bugun reaksiya vazifasini bajardingiz!", show_alert=True)
        return

    post_link = os.getenv("DAILY_POST_LINK", f"https://t.me/{MAIN_CHANNEL.lstrip('@')}")
    await cb.message.edit_text(
        f"❤️ <b>Reaksiya vazifasi</b>\n\n"
        f"Quyidagi postga <b>🔥</b> komment qoldiring:\n"
        f"{post_link}\n\n"
        f"Keyin «Tekshirish» tugmasini bosing.",
        reply_markup=kb(
            [{"text": "📢 Postga o'tish", "url": post_link}],
            [{"text": "✅ Tekshirish", "callback_data": "check_reaction"}],
            [{"text": "⬅️ Orqaga", "callback_data": "tasks"}],
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "check_reaction")
async def check_reaction(cb: CallbackQuery):
    # Production'da: Telegram API orqali kommentni tekshiring
    # Hozir: honor system — foydalanuvchi bajardi deb qabul qilamiz
    if await task_done_today(cb.from_user.id, "reaction"):
        await cb.answer("✅ Allaqachon bajarilgan!", show_alert=True)
        return

    total = await add_balls(cb.from_user.id, BALLS["post_reaction"], "reaction")
    await cb.message.edit_text(
        f"✅ <b>Bajarildi!</b> +{BALLS['post_reaction']} ball\n💰 Jami: <b>{total}</b>",
        reply_markup=kb([{"text": "⬅️ Menyuga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


# ── IMAGE TASK ────────────────────────────────
IMAGE_TASK_PLAYERS = [
    ("Akrom Afzaliyev",  "image_a"),
    ("Sardor Rashidov",  "image_b"),
    ("Aziz Xolmatov",   "image_c"),
    ("Bobur Mirzayev",  "image_d"),
]
IMAGE_TASK_CORRECT = "image_a"  # .env dan ham olinishi mumkin

@router.callback_query(F.data == "image_task")
async def show_image_task(cb: CallbackQuery):
    if await task_done_today(cb.from_user.id, "image_task"):
        await cb.answer("✅ Bugun bu vazifani bajardingiz!", show_alert=True)
        return

    shuffled = IMAGE_TASK_PLAYERS.copy()
    random.shuffle(shuffled)
    await cb.message.edit_text(
        "🔍 <b>Futbolchini toping!</b>\n\n"
        "Rasmda ko'rsatilgan Andijon FC futbolchisini aniqlang.\n"
        "(Rasmni kanaldan tekshiring: @AndijonFC)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=code)]
            for name, code in shuffled
        ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="tasks")]]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("image_"))
async def image_answer(cb: CallbackQuery):
    if await task_done_today(cb.from_user.id, "image_task"):
        await cb.answer("Allaqachon javob berdingiz!", show_alert=True)
        return

    # Log (noto'g'ri ham)
    try:
        await db_run(
            "INSERT INTO tasks (tg_id, task_type, task_date, balls) VALUES (?,?,?,?)",
            (cb.from_user.id, "image_task", today(), 0)
        )
    except Exception:
        pass

    if cb.data == IMAGE_TASK_CORRECT:
        total = await add_balls(cb.from_user.id, BALLS["image_task"], "image_task")
        text = f"✅ <b>To'g'ri!</b> +{BALLS['image_task']} ball\n💰 Jami: <b>{total}</b>"
    else:
        text = "❌ <b>Noto'g'ri.</b> Ertaga qayta urinib ko'ring!"

    await cb.message.edit_text(
        text,
        reply_markup=kb([{"text": "⬅️ Menyuga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


# ── REFERRAL ──────────────────────────────────
@router.callback_query(F.data == "referral")
async def show_referral(cb: CallbackQuery):
    ref_link = f"https://t.me/{(await cb.bot.get_me()).username}?start={cb.from_user.id}"
    ref_count = await db_get(
        "SELECT COUNT(*) AS cnt FROM users WHERE ref_by=?", (cb.from_user.id,)
    )
    cnt = ref_count["cnt"] if ref_count else 0

    await cb.message.edit_text(
        f"🔗 <b>Do'st taklif qilish</b>\n\n"
        f"Har taklif qilgan do'st uchun: <b>+{BALLS['referral']}</b> ball\n"
        f"Jami taklif qilganlar: <b>{cnt}</b> kishi\n\n"
        f"Sizning havolangiz:\n<code>{ref_link}</code>",
        reply_markup=kb([{"text": "⬅️ Orqaga", "callback_data": "back_main"}]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.edit_text(
        "Menyudan tanlang 👇",
        reply_markup=main_menu_kb()
    )


# ─────────────────────────────────────────────
# ADMIN BUYRUQLARI
# ─────────────────────────────────────────────
def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


@router.message(Command("stats"))
async def admin_stats(msg: Message):
    if not is_admin(msg.from_user.id):
        return

    total     = await db_get("SELECT COUNT(*) AS c FROM users WHERE is_banned=0")
    today_new = await db_get(
        "SELECT COUNT(*) AS c FROM users WHERE joined_at >= ? AND is_banned=0",
        (today(),)
    )
    active    = await db_get(
        "SELECT COUNT(*) AS c FROM users WHERE last_active=? AND is_banned=0",
        (today(),)
    )
    tasks_today = await db_get(
        "SELECT COUNT(*) AS c FROM tasks WHERE task_date=?", (today(),)
    )

    await msg.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami: {total['c']}\n"
        f"🆕 Bugun qo'shildi: {today_new['c']}\n"
        f"🟢 Bugun faol: {active['c']}\n"
        f"✅ Bugun bajarilgan vazifalar: {tasks_today['c']}",
        parse_mode="HTML"
    )


@router.message(Command("add_quiz"))
async def admin_add_quiz(msg: Message):
    """
    Format: /add_quiz Savol matni | A | B | C | D | to'g'ri_harf
    Misol:  /add_quiz 2024 yil chempioni kim? | Andijon | AGMK | Nasaf | PFC | a
    """
    if not is_admin(msg.from_user.id):
        return

    parts = msg.text.replace("/add_quiz ", "").split("|")
    parts = [p.strip() for p in parts]
    if len(parts) != 6:
        await msg.answer(
            "Format: /add_quiz Savol | A | B | C | D | to'g'ri_harf\n"
            "Misol: /add_quiz Kim g'olib? | Andijon | AGMK | Nasaf | PFC | a"
        )
        return

    q, a, b, c, d, ans = parts
    if ans not in ("a", "b", "c", "d"):
        await msg.answer("To'g'ri harf: a, b, c yoki d")
        return

    await db_run(
        "INSERT INTO quizzes (question, opt_a, opt_b, opt_c, opt_d, answer, active) VALUES (?,?,?,?,?,?,1)",
        (q, a, b, c, d, ans)
    )
    await msg.answer(f"✅ Savol qo'shildi: {q}")


@router.message(Command("giveaway"))
async def admin_giveaway(msg: Message, bot: Bot):
    """G'olibni weighted random usulda tanlash."""
    if not is_admin(msg.from_user.id):
        return

    users = await db_all(
        f"SELECT tg_id, name, balls FROM users "
        f"WHERE balls >= {MIN_BALLS_GIVEAWAY} AND is_banned=0"
    )

    # Kamida 3 ta vazifa bajarganlar
    eligible = []
    for u in users:
        task_count = await db_get(
            "SELECT COUNT(DISTINCT task_type) AS c FROM tasks WHERE tg_id=?",
            (u["tg_id"],)
        )
        if task_count and task_count["c"] >= 3:
            eligible.append(u)

    if not eligible:
        await msg.answer("⚠️ Hali hech kim minimal talabni bajarmagan.")
        return

    # Weighted pool: har 10 ball = 1 bilet (max 500)
    pool = []
    for u in eligible:
        tickets = min(u["balls"] // 10, 500)
        pool.extend([u["tg_id"]] * max(tickets, 1))

    winner_id = random.choice(pool)
    winner    = next(u for u in eligible if u["tg_id"] == winner_id)
    tickets_w = pool.count(winner_id)
    chance    = round(tickets_w / len(pool) * 100, 2)

    await db_run(
        "INSERT INTO giveaway_winners (tg_id, balls, tickets, total_pool) VALUES (?,?,?,?)",
        (winner_id, winner["balls"], tickets_w, len(pool))
    )

    # Admin xabari
    await msg.answer(
        f"🎉 <b>G'OLIB TANLANDI!</b>\n\n"
        f"👤 {winner['name']}\n"
        f"🏅 Ball: {winner['balls']}\n"
        f"🎫 Biletlar: {tickets_w} / {len(pool)}\n"
        f"📊 Yutish ehtimoli: {chance}%\n\n"
        f"Ishtirokchilar: {len(eligible)} kishi",
        parse_mode="HTML"
    )

    # G'olibga xabar
    try:
        await bot.send_message(
            winner_id,
            "🏆 <b>Tabriklaymiz!</b>\n\n"
            "Siz <b>Andijon FC Fan Challenge</b> g'olibi bo'ldingiz!\n"
            "Sovringizni olish uchun admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning(f"G'olibga xabar yuborib bo'lmadi: {e}")


@router.message(Command("ban"))
async def admin_ban(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("Format: /ban <tg_id>")
        return
    await db_run("UPDATE users SET is_banned=1 WHERE tg_id=?", (parts[1],))
    await msg.answer(f"✅ {parts[1]} ban qilindi.")


# ─────────────────────────────────────────────
# SCHEDULER — kunlik vazifalar
# ─────────────────────────────────────────────
async def broadcast_daily_quiz(bot: Bot):
    """Har kuni 09:00 — aktiv foydalanuvchilarga quiz yuborish."""
    quiz = await db_get(
        "SELECT * FROM quizzes WHERE is_flash=0 AND active=1 ORDER BY RANDOM() LIMIT 1"
    )
    if not quiz:
        return

    users = await db_all("SELECT tg_id FROM users WHERE is_banned=0 AND last_active IS NOT NULL")
    sent = 0
    for u in users:
        try:
            await bot.send_message(
                u["tg_id"],
                "🌅 <b>Kunlik viktorina vaqti!</b>\n\nBotga kiring va savolga javob bering 👇",
                reply_markup=kb([{"text": "🎯 Viktorinaga o'tish", "callback_data": "quiz"}]),
                parse_mode="HTML"
            )
            sent += 1
            await asyncio.sleep(0.05)  # flood limit
        except Exception:
            pass
    log.info(f"Daily quiz broadcast: {sent} users")


async def broadcast_flash_open(bot: Bot):
    """Har kuni 19:00 — tezkor savol ochiladi."""
    quiz = await db_get(
        "SELECT * FROM quizzes WHERE is_flash=1 AND active=1 ORDER BY RANDOM() LIMIT 1"
    )
    if not quiz:
        return

    await db_run(
        "INSERT INTO flash_sessions (quiz_id, opened_at) VALUES (?, ?)",
        (quiz["id"], datetime.now().isoformat())
    )

    opts = [
        (f"A) {quiz['opt_a']}", f"fq_{quiz['id']}_a"),
        (f"B) {quiz['opt_b']}", f"fq_{quiz['id']}_b"),
        (f"C) {quiz['opt_c']}", f"fq_{quiz['id']}_c"),
        (f"D) {quiz['opt_d']}", f"fq_{quiz['id']}_d"),
    ]
    users = await db_all("SELECT tg_id FROM users WHERE is_banned=0")
    for u in users:
        try:
            await bot.send_message(
                u["tg_id"],
                f"⚡ <b>TEZKOR SAVOL!</b> (5 daqiqa)\n\n{quiz['question']}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=t, callback_data=d)] for t, d in opts
                ]),
                parse_mode="HTML"
            )
            await asyncio.sleep(0.05)
        except Exception:
            pass


async def broadcast_flash_close(bot: Bot):
    """Har kuni 19:05 — tezkor savol yopiladi."""
    session = await db_get("SELECT * FROM flash_sessions WHERE active=1")
    if session:
        await db_run(
            "UPDATE flash_sessions SET active=0, closed_at=? WHERE id=?",
            (datetime.now().isoformat(), session["id"])
        )


@router.callback_query(F.data.startswith("fq_"))
async def flash_answer(cb: CallbackQuery):
    session = await db_get("SELECT * FROM flash_sessions WHERE active=1")
    if not session:
        await cb.answer("⏰ Vaqt tugadi!", show_alert=True)
        return

    if await task_done_today(cb.from_user.id, "flash"):
        await cb.answer("Allaqachon javob berdingiz!", show_alert=True)
        return

    _, quiz_id, chosen = cb.data.split("_")
    quiz = await db_get("SELECT * FROM quizzes WHERE id=?", (quiz_id,))
    if not quiz:
        return

    try:
        await db_run(
            "INSERT INTO tasks (tg_id, task_type, task_date, balls) VALUES (?,?,?,?)",
            (cb.from_user.id, "flash", today(), 0)
        )
    except Exception:
        await cb.answer("Allaqachon javob berdingiz!", show_alert=True)
        return

    if chosen == quiz["answer"]:
        total = await add_balls(cb.from_user.id, BALLS["flash_correct"], "flash")
        badge_msg = await award_badge(cb.from_user.id, "speed_demon")
        text = f"⚡ <b>To'g'ri!</b> +{BALLS['flash_correct']} ball\n💰 Jami: <b>{total}</b>"
        if badge_msg:
            text += f"\n\n{badge_msg}"
    else:
        correct_opt = quiz["opt_" + quiz["answer"]]
        text = f"❌ <b>Noto'g'ri.</b> To'g'ri javob: {correct_opt}"

    await cb.answer(text[:200], show_alert=True)


async def update_streaks():
    """Har kuni 23:55 — seriyalarni yangilash."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    active_yesterday = await db_all(
        "SELECT tg_id FROM users WHERE last_active=?", (yesterday,)
    )
    active_ids = {u["tg_id"] for u in active_yesterday}

    all_users = await db_all("SELECT tg_id, streak FROM users WHERE is_banned=0")
    for u in all_users:
        if u["tg_id"] in active_ids:
            new_streak = u["streak"] + 1
            await db_run(
                "UPDATE users SET streak=? WHERE tg_id=?",
                (new_streak, u["tg_id"])
            )
            if new_streak >= 3:
                await add_balls(u["tg_id"], BALLS["streak_bonus"], "streak_bonus")
                await award_badge(u["tg_id"], "streak_3")
        else:
            await db_run("UPDATE users SET streak=0 WHERE tg_id=?", (u["tg_id"],))


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = "Asia/Tashkent"
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(broadcast_daily_quiz,  CronTrigger(hour=9,  minute=0,  timezone=tz), args=[bot])
    scheduler.add_job(broadcast_flash_open,  CronTrigger(hour=19, minute=0,  timezone=tz), args=[bot])
    scheduler.add_job(broadcast_flash_close, CronTrigger(hour=19, minute=5,  timezone=tz), args=[bot])
    scheduler.add_job(update_streaks,        CronTrigger(hour=23, minute=55, timezone=tz))
    return scheduler


# ─────────────────────────────────────────────
# APP STARTUP
# ─────────────────────────────────────────────
async def on_startup(bot: Bot):
    await init_db()
    log.info("DB initialized")
    if WEBHOOK_HOST:
        url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
        log.info(f"Webhook set: {url}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()


def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    if WEBHOOK_HOST:
        # Railway / Render — webhook mode
        app = web.Application()
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
        handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
    else:
        # Local — polling mode
        asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()

import os
from sqlalchemy import DateTime
import asyncio
import logging
from sqlalchemy import select
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import DateTime
from datetime import datetime
from sqlalchemy import Date
from datetime import date
from datetime import date, timedelta
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from datetime import date
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker
)
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column
)

from sqlalchemy import (
    BigInteger,
    Integer,
    String
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [
    515902673,
    7988918836
]

MAIN_CHANNEL = "@andijonpfc"

logging.basicConfig(level=logging.INFO)

DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+asyncpg://"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass

#user bo`limi manashuyerdaaa



match_create_admins = {}
prediction_states = {}
result_states = {}
edit_prediction_states = {}
quiz_create_states = {}




class QuizAnswer(Base):

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger
    )

    quiz_id: Mapped[int] = mapped_column(
        Integer
    )





class Quiz(Base):

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    question: Mapped[str] = mapped_column(
        String(500)
    )

    option_a: Mapped[str] = mapped_column(
        String(255)
    )

    option_b: Mapped[str] = mapped_column(
        String(255)
    )

    option_c: Mapped[str] = mapped_column(
        String(255)
    )

    option_d: Mapped[str] = mapped_column(
        String(255)
    )

    correct_answer: Mapped[str] = mapped_column(
        String(1)
    )

    reward: Mapped[int] = mapped_column(
        Integer,
        default=10
    )

    active: Mapped[bool] = mapped_column(
        default=True
    )




class Match(Base):

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    home_team: Mapped[str] = mapped_column(
        String(100)
    )

    away_team: Mapped[str] = mapped_column(
        String(100)
    )

    match_date: Mapped[datetime] = mapped_column(
        DateTime
    )

    active: Mapped[bool] = mapped_column(
        default=True
    )

    result: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )




class Prediction(Base):

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger
    )

    match_id: Mapped[int] = mapped_column(
        Integer
    )

    score: Mapped[str] = mapped_column(
        String(20)
    )





class User(Base):

    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(255)
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    balls: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    referrals: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    
    ref_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )
    
    last_bonus: Mapped[datetime | None] = mapped_column(
    DateTime,
    nullable=True
    )
    bonus_streak: Mapped[int] = mapped_column(
        Integer,
        default=0
    )



async def check_subscription(user_id):

    try:

        member = await bot.get_chat_member(
            MAIN_CHANNEL,
            user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

    except:

        return False

async def get_or_create_user(
    message: Message,
    ref_id=None
):

    async with SessionLocal() as session:

        user = await session.get(
            User,
            message.from_user.id
        )

        if user:
            return user

        user = User(
            tg_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            ref_by=ref_id
        )

        session.add(user)

        if (
            ref_id
            and ref_id != message.from_user.id
        ):

            ref_user = await session.get(
                User,
                ref_id
            )

            if ref_user:

                ref_user.referrals += 1
                ref_user.balls += 30

        await session.commit()

        return user


async def create_tables():

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎯 Viktorina"),
            KeyboardButton(text="📋 Vazifalar")
        ],
        [
            KeyboardButton(text="🏆 Reyting"),
            KeyboardButton(text="👤 Profilim")
        ],
        [
            KeyboardButton(text="🔥 Kunlik Bonus"),
            KeyboardButton(text="⚽ Match Prognoz")
        ],
        [
            KeyboardButton(text="📊 Mening Prognozlarim")
        ],
        [
            KeyboardButton(text="🎁 Sovrinlar"),
            KeyboardButton(text="🔗 Taklif qilish")
        ]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="➕ Savol qo'shish"),
            KeyboardButton(text="📊 Statistika"),
        ],
        [
            KeyboardButton(text="🏁 Natija Kiritish")
        ],
        [
            KeyboardButton(text="📢 Xabar yuborish"),
            KeyboardButton(text="🎁 G'olib tanlash")
        ],
        [
            KeyboardButton(text="⚽ Match Yaratish")
        ],
        [
            KeyboardButton(text="⬅️ Asosiy menyu")
        ]
    ],
    resize_keyboard=True
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()

@dp.callback_query(
    F.data == "check_sub"
)
async def check_sub_callback(
    callback: CallbackQuery
):

    if await check_subscription(
        callback.from_user.id
    ):

        await callback.message.delete()

        await callback.message.answer(
            "✅ Obuna tasdiqlandi.\n"
            "Botdan foydalanishingiz mumkin.",
            reply_markup=user_menu
        )

    else:

        await callback.answer(
            "❌ Hali kanalga obuna bo'lmagansiz.",
            show_alert=True
        )



# START KOMANDASI BOTNI ISHLATISH



@dp.message(CommandStart())
async def start_cmd(message: Message):

    if not await check_subscription(
        message.from_user.id
    ):

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📢 Kanalga o'tish",
                        url=f"https://t.me/{MAIN_CHANNEL.replace('@','')}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Tekshirish",
                        callback_data="check_sub"
                    )
                ]
            ]
        )

        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalga obuna bo'ling.",
            reply_markup=kb
        )

        return

    ref_id = None

    args = message.text.split()

    if len(args) > 1:

        if args[1].isdigit():

            ref_id = int(args[1])

    await get_or_create_user(
        message,
        ref_id
    )

    if message.from_user.id in ADMIN_IDS:

        await message.answer(
            "⚽ Admin panel",
            reply_markup=admin_menu
        )

    else:

        await message.answer(
            "⚽ Andijon FC Fan Challenge\n\n"
            "Ball yig'ing va sovg'alarni qo'lga kiriting!",
            reply_markup=user_menu
        )


# PROFIL TUGMASI MENYUSI



@dp.message(F.text == "👤 Profilim")
async def profile_handler(message: Message):

    async with SessionLocal() as session:

        user = await session.get(
            User,
            message.from_user.id
        )

        result = await session.execute(
            select(User)
            .order_by(User.balls.desc())
        )

        users = result.scalars().all()

        place = 0

        for i, u in enumerate(users, start=1):

            if u.tg_id == user.tg_id:

                place = i
                break

    await message.answer(
        f"👤 Profil\n\n"
        f"🏅 Ball: {user.balls}\n"
        f"👥 Referral: {user.referrals}\n"
        f"🏆 O‘rin: #{place}\n\n"
        f"🎁 TOP 3 sovrin oladi"
    )
    


# REYTING MENUSI TUGMASI




@dp.message(F.text == "🏆 Reyting")
async def leaderboard_handler(message: Message):

    async with SessionLocal() as session:

        result = await session.execute(
            select(Quiz)
            .where(Quiz.active == True)
            .order_by(Quiz.id.desc())
            .limit(1)
        )
        
        quiz = result.scalar()

    text = "🏆 TOP 10\n\n"

    for i, user in enumerate(users, start=1):

        text += (
            f"{i}. "
            f"{user.full_name} - "
            f"{user.balls} ball\n"
        )

    await message.answer(text)


# referal linkt tugmasi funktsiyasi



@dp.message(F.text == "🔗 Taklif qilish")
async def referral_handler(message: Message):

    me = await bot.get_me()

    link = (
        f"https://t.me/"
        f"{me.username}"
        f"?start={message.from_user.id}"
    )

    async with SessionLocal() as session:

        user = await session.get(
            User,
            message.from_user.id
        )

    await message.answer(
        f"🔗 Sizning referral linkingiz:\n\n"
        f"{link}\n\n"
        f"👥 Taklif qilganlar: "
        f"{user.referrals}\n\n"
        f"🏅 Har do'st uchun +30 ball"
    )


# KUNLIK BONUSLAR BOLIMI VA FUNKTSIYASI




@dp.message(F.text == "🔥 Kunlik Bonus")
async def daily_bonus(message: Message):

    async with SessionLocal() as session:

        user = await session.get(
            User,
            message.from_user.id
        )

        today = date.today()

        if user.last_bonus == today:

            await message.answer(
                "❌ Siz bugungi bonusni olib bo'lgansiz."
            )
            return

        if user.last_bonus:

            diff = (
                today - user.last_bonus
            ).days

            if diff == 1:

                user.bonus_streak += 1

            else:

                user.bonus_streak = 1

        else:

            user.bonus_streak = 1

        reward = min(
            user.bonus_streak * 5,
            50
        )

        user.balls += reward
        user.last_bonus = today

        await session.commit()

        await message.answer(
            f"🔥 Kunlik bonus olindi!\n\n"
            f"📅 Ketma-ket kunlar: "
            f"{user.bonus_streak}\n"
            f"🏅 Bonus: +{reward} ball\n"
            f"🎯 Jami ball: {user.balls}"
        )

#sovrinlar tugmmasi va oshani menyusi



@dp.message(F.text == "🎁 Sovrinlar")
async def prizes_handler(message: Message):

    await message.answer(
        "🎁 Sovrinlar\n\n"
        "🥇 1-o‘rin\n"
        "👕 Futbolchi imzoli futbolka\n\n"
        "🥈 2-o‘rin\n"
        "🧣 Klub sharfi\n\n"
        "🥉 3-o‘rin\n"
        "🎫 Stadion chiptasi\n\n"
        "🏆 Ball yig‘ing va TOP 3 ga kiring!"
    )


#vazifalarim tugmasi va menyusi



@dp.message(F.text == "📋 Vazifalar")
async def tasks_handler(message: Message):

    await message.answer(
        "📋 Bugungi vazifalar\n\n"
        "🔥 Kunlik bonus oling (+5)\n"
        "👥 Do‘st taklif qiling (+30)\n"
        "⚽ Match prognoz qiling (+50)\n\n"
        "Ko‘proq ball = sovringa yaqinroq"
    )



@dp.message(F.text == "⚽ Match Yaratish")
async def create_match(message: Message):

    if message.from_user.id not in ADMIN_IDS:
        return

    match_create_admins[message.from_user.id] = {
        "step": 1
    }

    await message.answer(
        "Jamoalarni kiriting\n\n"
        "Misol:\n"
        "Andijon-Nasaf"
    )


@dp.message(
    lambda m:
    m.from_user.id in match_create_admins
)
async def create_match_steps(message: Message):

    if message.from_user.id not in match_create_admins:
        return

    state = match_create_admins[
        message.from_user.id
    ]

    if state["step"] == 1:

        if "-" not in message.text:

            await message.answer(
                "Misol:\nAndijon-Nasaf"
            )
            return

        home, away = message.text.split("-", 1)

        state["home"] = home.strip()
        state["away"] = away.strip()
        state["step"] = 2

        await message.answer(
            "Sana va vaqt kiriting\n\n"
            "Misol:\n"
            "2025-08-20 20:00"
        )

        return

    if state["step"] == 2:

        try:

            match_date = datetime.strptime(
                message.text.strip(),
                "%Y-%m-%d %H:%M"
            )

        except:

            await message.answer(
                "Format:\n2025-08-20 20:00"
            )
            return

        async with SessionLocal() as session:

            match = Match(
                home_team=state["home"],
                away_team=state["away"],
                match_date=match_date,
                active=True
            )

            session.add(match)

            await session.commit()

        del match_create_admins[
            message.from_user.id
        ]

        await message.answer(
            f"✅ Match yaratildi\n\n"
            f"⚽ {state['home']} vs {state['away']}\n"
            f"📅 {match_date.strftime('%d.%m.%Y %H:%M')}"
        )


@dp.message(F.text == "🏁 Natija Kiritish")
async def result_menu(message: Message):

    if message.from_user.id not in ADMIN_IDS:
        return

    async with SessionLocal() as session:

        result = await session.execute(
            select(Match)
            .where(Match.active == True)
            .order_by(Match.match_date)
        )

        matches = result.scalars().all()

    if not matches:

        await message.answer(
            "❌ Aktiv o'yinlar yo'q"
        )
        return

    keyboard = []

    for match in matches:

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⚽ {match.home_team} vs {match.away_team}",
                    callback_data=f"result_{match.id}"
                )
            ]
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )

    await message.answer(
        "🏁 Natija kiritiladigan matchni tanlang",
        reply_markup=kb
    )


def get_winner(score):

    home, away = map(int, score.split(":"))

    if home > away:
        return "home"

    if home < away:
        return "away"

    return "draw"



@dp.callback_query(
    F.data.startswith("result_")
)
async def result_callback(
    callback: CallbackQuery
):

    match_id = int(
        callback.data.split("_")[1]
    )

    result_states[
        callback.from_user.id
    ] = {
        "match_id": match_id
    }

    async with SessionLocal() as session:

        match = await session.get(
            Match,
            match_id
        )

    await callback.message.answer(
        f"⚽ {match.home_team} vs {match.away_team}\n\n"
        f"Natijani kiriting\n"
        f"Misol: 2:1"
    )

    await callback.answer()

@dp.message(
    lambda m:
    m.from_user.id in result_states
)
async def save_result(
    message: Message
):

    score = message.text.strip()

    if ":" not in score:

        await message.answer(
            "Misol: 2:1"
        )
        return

    async with SessionLocal() as session:

        state = result_states[
            message.from_user.id
        ]

        match = await session.get(
            Match,
            state["match_id"]
        )

        match.result = score
        match.active = False

        result = await session.execute(
            select(Prediction)
            .where(
                Prediction.match_id == match.id
            )
        )

        predictions = result.scalars().all()

        for prediction in predictions:

            user = await session.get(
                User,
                prediction.user_id
            )

            reward = 0

            if prediction.score == score:

                reward = 100

            elif (
                get_winner(prediction.score)
                ==
                get_winner(score)
            ):

                reward = 40

            user.balls += reward

            try:

                if reward > 0:

                    await bot.send_message(
                        prediction.user_id,
                        f"🎉 Prognoz natijasi!\n\n"
                        f"⚽ {match.home_team} vs {match.away_team}\n"
                        f"🏁 Natija: {score}\n\n"
                        f"🏅 Siz +{reward} ball oldingiz!"
                    )

            except:
                pass

        await session.commit()

    del result_states[
        message.from_user.id
    ]

    await message.answer(
        f"✅ Natija saqlandi\n\n"
        f"⚽ {match.home_team} vs {match.away_team}\n"
        f"🏁 {score}"
    )



@dp.message(F.text == "⚽ Match Prognoz")
async def prediction_menu(message: Message):

    async with SessionLocal() as session:

        result = await session.execute(
            select(Match)
            .where(Match.active == True)
            .order_by(Match.match_date)
        )

        matches = result.scalars().all()

    if not matches:

        await message.answer(
            "❌ Hozir aktiv o'yinlar yo'q"
        )
        return

    keyboard = []

    for match in matches:

        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"⚽ {match.home_team} vs {match.away_team}",
                    callback_data=f"predict_{match.id}"
                )
            ]
        )

    kb = InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )

    await message.answer(
        "⚽ Prognoz uchun match tanlang",
        reply_markup=kb
    )



@dp.callback_query(
    F.data.startswith("predict_")
)
async def prediction_callback(
    callback: CallbackQuery
):

    match_id = int(
        callback.data.split("_")[1]
    )

    prediction_states[
        callback.from_user.id
    ] = {
        "match_id": match_id
    }

    async with SessionLocal() as session:

        match = await session.get(
            Match,
            match_id
        )

    await callback.message.answer(
        f"⚽ {match.home_team} vs {match.away_team}\n\n"
        f"Hisob kiriting\n"
        f"Misol: 2:1"
    )

    await callback.answer()


@dp.message(
    lambda m:
    m.from_user.id in prediction_states
)
async def save_prediction(
    message: Message
):

    score = message.text.strip()

    if ":" not in score:

        await message.answer(
            "Misol: 2:1"
        )
        return

    async with SessionLocal() as session:

        state = prediction_states[
            message.from_user.id
        ]

        match = await session.get(
            Match,
            state["match_id"]
        )

        if datetime.now() >= match.match_date:

            del prediction_states[
                message.from_user.id
            ]

            await message.answer(
                "❌ Match boshlangan."
            )
            return

        result = await session.execute(
            select(Prediction)
            .where(
                Prediction.user_id ==
                message.from_user.id,
                Prediction.match_id ==
                state["match_id"]
            )
        )

        prediction = result.scalar_one_or_none()

        if prediction:

            prediction.score = score

        else:

            session.add(
                Prediction(
                    user_id=message.from_user.id,
                    match_id=state["match_id"],
                    score=score
                )
            )

        await session.commit()

    del prediction_states[
        message.from_user.id
    ]

    await message.answer(
        f"✅ Prognoz saqlandi\n\n"
        f"📊 Sizning prognozingiz: {score}"
    )




@dp.message(F.text == "📊 Mening Prognozlarim")
async def my_predictions(message: Message):

    async with SessionLocal() as session:

        result = await session.execute(
            select(Prediction, Match)
            .join(
                Match,
                Prediction.match_id == Match.id
            )
            .where(
                Prediction.user_id ==
                message.from_user.id,
                Match.active == True
            )
        )

        rows = result.all()

    if not rows:

        await message.answer(
            "📭 Aktiv prognozlaringiz yo'q."
        )
        return

    for prediction, match in rows:

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✏️ O'zgartirish",
                        callback_data=
                        f"edit_{match.id}"
                    )
                ]
            ]
        )

        await message.answer(
            f"⚽ {match.home_team} vs "
            f"{match.away_team}\n"
            f"📅 {match.match_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"📊 Prognoz: {prediction.score}",
            reply_markup=kb
        )

@dp.callback_query(
    F.data.startswith("edit_")
)
async def edit_prediction_callback(
    callback: CallbackQuery
):

    match_id = int(
        callback.data.split("_")[1]
    )

    edit_prediction_states[
        callback.from_user.id
    ] = {
        "match_id": match_id
    }

    await callback.message.answer(
        "Yangi prognozni kiriting\n\n"
        "Misol: 3:1"
    )

    await callback.answer()


@dp.message(
    lambda m:
    m.from_user.id in edit_prediction_states
)
async def save_edited_prediction(
    message: Message
):

    score = message.text.strip()

    if ":" not in score:

        await message.answer(
            "Misol: 2:1"
        )
        return

    async with SessionLocal() as session:

        state = edit_prediction_states[
            message.from_user.id
        ]

        match = await session.get(
            Match,
            state["match_id"]
        )

        if datetime.now() >= match.match_date:

            del edit_prediction_states[
                message.from_user.id
            ]

            await message.answer(
                "❌ Match boshlangan.\n"
                "Prognozni o'zgartirib bo'lmaydi."
            )
            return

        result = await session.execute(
            select(Prediction)
            .where(
                Prediction.user_id ==
                message.from_user.id,
                Prediction.match_id ==
                state["match_id"]
            )
        )

        prediction = result.scalar_one()

        prediction.score = score

        await session.commit()

    del edit_prediction_states[
        message.from_user.id
    ]

    await message.answer(
        f"✅ Prognoz yangilandi\n\n"
        f"📊 Yangi prognoz: {score}"
    )



@dp.message(F.text == "➕ Savol qo'shish")
async def add_quiz(message: Message):

    if message.from_user.id not in ADMIN_IDS:
        return

    quiz_create_states[
        message.from_user.id
    ] = {
        "step": 1
    }

    await message.answer(
        "Savolni kiriting:"
    )

@dp.message(
    lambda m:
    m.from_user.id in quiz_create_states
)
async def quiz_create_steps(
    message: Message
):

    state = quiz_create_states[
        message.from_user.id
    ]

    if state["step"] == 1:

        state["question"] = message.text
        state["step"] = 2

        await message.answer(
            "A variant:"
        )
        return

    if state["step"] == 2:

        state["a"] = message.text
        state["step"] = 3

        await message.answer(
            "B variant:"
        )
        return

    if state["step"] == 3:

        state["b"] = message.text
        state["step"] = 4

        await message.answer(
            "C variant:"
        )
        return

    if state["step"] == 4:

        state["c"] = message.text
        state["step"] = 5

        await message.answer(
            "D variant:"
        )
        return

    if state["step"] == 5:

        state["d"] = message.text
        state["step"] = 6

        await message.answer(
            "To'g'ri javob:\n\nA/B/C/D"
        )
        return

    if state["step"] == 6:

        answer = message.text.upper()

        if answer not in [
            "A",
            "B",
            "C",
            "D"
        ]:

            await message.answer(
                "Faqat A/B/C/D"
            )
            return

        state["correct"] = answer
        state["step"] = 7

        await message.answer(
            "Ball miqdori:"
        )
        return

    if state["step"] == 7:

        if not message.text.isdigit():

            await message.answer(
                "Raqam kiriting"
            )
            return

        reward = int(message.text)

        async with SessionLocal() as session:

            quiz = Quiz(
                question=state["question"],
                option_a=state["a"],
                option_b=state["b"],
                option_c=state["c"],
                option_d=state["d"],
                correct_answer=state["correct"],
                reward=reward,
                active=True
            )

            session.add(quiz)

            await session.commit()

        del quiz_create_states[
            message.from_user.id
        ]

        await message.answer(
            "✅ Savol saqlandi"
        )


@dp.message(F.text == "🎯 Viktorina")
async def quiz_menu(message: Message):

    async with SessionLocal() as session:

        result = await session.execute(
            select(Quiz)
            .where(Quiz.active == True)
            .order_by(Quiz.id.desc())
        )

        quiz = result.scalar_one_or_none()

        if not quiz:

            await message.answer(
                "❌ Hozir aktiv viktorina yo'q"
            )
            return

        check = await session.execute(
            select(QuizAnswer)
            .where(
                QuizAnswer.user_id
                == message.from_user.id,
                QuizAnswer.quiz_id
                == quiz.id
            )
        )

        answered = check.scalar_one_or_none()

        if answered:

            await message.answer(
                "✅ Siz bu savolga javob bergansiz."
            )
            return

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=quiz.option_a,
                        callback_data=f"quiz_{quiz.id}_A"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=quiz.option_b,
                        callback_data=f"quiz_{quiz.id}_B"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=quiz.option_c,
                        callback_data=f"quiz_{quiz.id}_C"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=quiz.option_d,
                        callback_data=f"quiz_{quiz.id}_D"
                    )
                ]
            ]
        )

        await message.answer(
            f"🏆 <b>ANDIJON FC VIKTORINASI</b>\n\n"
            f"❓ <b>{quiz.question}</b>\n\n"
            f"🏅 Mukofot: <b>{quiz.reward} ball</b>",
            reply_markup=kb
        )



@dp.callback_query(
    F.data.startswith("quiz_")
)
async def quiz_answer(
    callback: CallbackQuery
):

    _, quiz_id, answer = (
        callback.data.split("_")
    )

    quiz_id = int(quiz_id)

    async with SessionLocal() as session:

        quiz = await session.get(
            Quiz,
            quiz_id
        )

        check = await session.execute(
            select(QuizAnswer)
            .where(
                QuizAnswer.user_id
                == callback.from_user.id,
                QuizAnswer.quiz_id
                == quiz_id
            )
        )

        if check.scalar_one_or_none():

            await callback.answer(
                "Siz javob bergansiz",
                show_alert=True
            )
            return

        session.add(
            QuizAnswer(
                user_id=callback.from_user.id,
                quiz_id=quiz_id
            )
        )

        user = await session.get(
            User,
            callback.from_user.id
        )

        if answer == quiz.correct_answer:

            user.balls += quiz.reward

            text = (
                f"✅ To'g'ri javob!\n\n"
                f"🏅 +{quiz.reward} ball oldingiz."
            )

        else:

            text = (
                f"❌ Noto'g'ri javob.\n\n"
                f"To'g'ri javob: "
                f"{quiz.correct_answer}"
            )

        await session.commit()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(text)

    await callback.answer()






async def main():

    await create_tables()

    await bot.delete_webhook(
        drop_pending_updates=True
    )
    
    await dp.start_polling(bot)
    print("BOT STARTED")

if __name__ == "__main__":
    asyncio.run(main())

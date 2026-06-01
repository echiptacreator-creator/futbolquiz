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
     
    prediction: Mapped[str | None] = mapped_column(
    String(20),
    nullable=True
    )




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



# START KOMANDASI BOTNI ISHLATISH




@dp.message(CommandStart())
async def start_cmd(message: Message):

    ref_id = None

    args = message.text.split()

    if len(args) > 1:

        if args[1].isdigit():

            ref_id = int(args[1])

    print("START =", message.text)
    print("USER =", message.from_user.id)
    print("REF =", ref_id)

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
            select(User)
            .order_by(User.balls.desc())
            .limit(10)
        )

        users = result.scalars().all()

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
                "⏳ Siz bugungi bonusni olib bo'lgansiz.\n\n"
                "Ertaga qayting."
            )
            return
        
        user.balls += 5
        user.last_bonus = today
        
        await session.commit()
        
        await message.answer(
            "🔥 Bonus olindi!\n\n"
            "🏅 +5 ball"
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


@dp.message()
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





async def main():

    await create_tables()

    await bot.delete_webhook(
        drop_pending_updates=True
    )
    
    await dp.start_polling(bot)
    print("BOT STARTED")

if __name__ == "__main__":
    asyncio.run(main())

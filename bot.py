import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)

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
    int(x)
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x
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
            KeyboardButton(text="📊 Statistika")
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

@dp.message(CommandStart())
async def start_cmd(message: Message):

    await message.answer(
        "⚽ Andijon FC Fan Challenge\n\n"
        "Ball yig'ing va sovg'alarni qo'lga kiriting!",
        reply_markup=user_menu
    )












async def main():

    await create_tables()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import *

# ---------------- WEB SERVER ---------------- #

routes = web.RouteTableDef()

@routes.get("/")
async def root_handler(request):
    return web.json_response("Rohit")

async def start_web_server():
    app = web.Application(client_max_size=9000000000)
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

# ---------------- BOT INIT ---------------- #

bot = Bot(
    token=TG_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# ---------------- MAIN MENU KEYBOARD ---------------- #

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔎 Search Manga")],
            [KeyboardButton(text="❌ Close")],
            [KeyboardButton(text="💻 Contact Developer")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

# ---------------- START COMMAND ---------------- #

@dp.message(F.text == "/start")
async def start_command(message: Message):

    await message.answer_photo(
        photo=START_PIC,
        caption=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=f"@{message.from_user.username}" if message.from_user.username else "None",
            mention=message.from_user.mention_html(),
            id=message.from_user.id
        ),
        reply_markup=main_menu()
    )

# ---------------- BUTTON HANDLERS ---------------- #

@dp.message(F.text == "🔎 Search Manga")
async def search_manga(message: Message):
    await message.answer(
        "Send manga name to search 🔍",
        reply_markup=main_menu()
    )

@dp.message(F.text == "💻 Contact Developer")
async def contact_dev(message: Message):
    await message.answer(
        "Developer: https://t.me/rohit_1888",
        reply_markup=main_menu()
    )

@dp.message(F.text == "❌ Close")
async def close_menu(message: Message):
    await message.answer(
        "Menu Closed ❌",
        reply_markup=ReplyKeyboardRemove()
    )

# ---------------- MAIN ---------------- #

async def main():
    await start_web_server()
    print("Bot running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
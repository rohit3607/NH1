import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import *

# ---------------- WEB SERVER ---------------- #

routes = web.RouteTableDef()

@routes.get("/")
async def root_handler(request):
    return web.json_response({"status": "Rohit Bot Running"})

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

# ---------------- KEYBOARDS ---------------- #

def start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Channel",
                    url="https://t.me/yourchannel",
                    button_style="primary"      # 🔵 Blue
                )
            ],
            [
                InlineKeyboardButton(
                    text="🫶 Donate At Your Will",
                    url="https://t.me/yourdonate",
                    button_style="success"      # 🟢 Green
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ About",
                    callback_data="about",
                    button_style="secondary"    # ⚪ Gray
                )
            ]
        ]
    )

def about_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="back",
                    button_style="destructive"  # 🔴 Red
                )
            ]
        ]
    )

# ---------------- START HANDLER ---------------- #

@dp.message(F.text == "/start")
async def start_command(message: Message):

    caption = f"""
<b>Hey {message.from_user.first_name} 👋</b>

I am a <b>Manga Downloader Bot</b> 📚  
Search and download manga instantly ⚡

Click the buttons below to continue.
"""

    await message.answer_photo(
        photo=START_PIC,
        caption=caption,
        reply_markup=start_keyboard()
    )

# ---------------- ABOUT CALLBACK ---------------- #

@dp.callback_query(F.data == "about")
async def about_callback(call: CallbackQuery):
    await call.answer()

    await call.message.edit_caption(
        caption="""
<b>📌 About This Bot</b>

• Fast Manga Search  
• Instant Download  
• Clean Interface  
• Developed by <a href="https://t.me/rohit_1888">Rohit</a>
""",
        reply_markup=about_keyboard()
    )

# ---------------- BACK CALLBACK ---------------- #

@dp.callback_query(F.data == "back")
async def back_callback(call: CallbackQuery):
    await call.answer()

    caption = f"""
<b>Hey {call.from_user.first_name} 👋</b>

I am a <b>Manga Downloader Bot</b> 📚  
Search and download manga instantly ⚡

Click the buttons below to continue.
"""

    await call.message.edit_caption(
        caption=caption,
        reply_markup=start_keyboard()
    )

# ---------------- MAIN ---------------- #

async def main():
    await start_web_server()
    print("Bot running with Bot API 9.4 styled buttons...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
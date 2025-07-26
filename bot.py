from aiohttp import web
import asyncio, os, re
from urllib.parse import urlparse
import math
import tempfile
#from tqdm import tqdm
from tqdm.asyncio import tqdm
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import subprocess, sys
import cloudscraper
#from playwright.async_api import async_playwright
import aiohttp
import json
import pyromod.listen
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from time import time
from pyrogram.enums import ParseMode
from pyrogram.types import (
    Message, CallbackQuery, InlineQueryResultArticle,
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
)

# ---------------- CONFIG ---------------- #
from config import *  # Define APP_ID, API_HASH, TG_BOT_TOKEN, OWNER_ID, PORT, LOGGER, START_MSG, START_PIC
from database import *  # Your database file

# ---------------- WEB SERVER ---------------- #
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_handler(request):
    return web.json_response("Rohit")

async def web_server():
    web_app = web.Application(client_max_size=9000000000)
    web_app.add_routes(routes)
    return web_app

# ---------------- BOT INIT ---------------- #
class Bot(Client):
    def __init__(self):
        super().__init__(
            name="nhentaiBot",
            api_id=APP_ID,
            api_hash=API_HASH,
            bot_token=TG_BOT_TOKEN,
            workers=4
        )
        self.LOGGER = LOGGER

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.set_parse_mode(ParseMode.HTML)
        self.username = me.username
        self.uptime = datetime.now()
        self.LOGGER(__name__).info(f"Bot Running...! @{self.username}")

        runner = web.AppRunner(await web_server())
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()

        try:
            await self.send_message(OWNER_ID, "<b><blockquote>Bot restarted.</blockquote></b>")
        except:
            pass

    async def stop(self):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")

    def run(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.LOGGER(__name__).info("Interrupted.")
        finally:
            loop.run_until_complete(self.stop())

app = Bot()

# ---------------- START HANDLER ---------------- #
@app.on_message(filters.command('start') & filters.private)
async def start_command(_, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Search Manga", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("💻 Contact Developer", url="https://t.me/rohit_1888")]
    ])
    await message.reply_photo(
        photo=START_PIC,
        caption=START_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=('@' + message.from_user.username) if message.from_user.username else None,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=keyboard
    )

# ---------------- INLINE SEARCH ---------------- #
@app.on_message(filters.command("download") & filters.private)
async def megaup_handler(client, message: Message):
    urls = re.findall(r'https?://megaup\.cc/download/\S+', message.text)
    if not urls:
        return await message.reply("❌ No valid MegaUp link found.")
    
    for url in urls:
        await parse_megaup_page(client, message, url)

async def parse_megaup_page(client, message, url):
    scraper = cloudscraper.create_scraper()
    try:
        html = scraper.get(url).text
        soup = BeautifulSoup(html, "html.parser")

        # Sometimes there's only one button with id="downloadButton"
        direct_button = soup.find("a", {"id": "downloadButton"})
        if direct_button and direct_button.has_attr("href"):
            file_name = soup.find("span", class_="filename")
            file_size = soup.find("span", class_="filesize")
            name = file_name.text.strip() if file_name else "Unknown"
            size = file_size.text.strip() if file_size else "Unknown"
            buttons = [[InlineKeyboardButton(f"📥 {name} ({size})", callback_data=f"wait30|{url}|{name}")]]
            return await message.reply(
                f"<b>📄 File:</b> <code>{name}</code>\n<b>📦 Size:</b> <code>{size}</code>",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # If multiple quality/links are available, we look for divs or a tags inside link containers
        all_buttons = soup.find_all("a", href=re.compile(r"^/download/\w+/\w+"))
        if not all_buttons:
            return await message.reply("❌ No downloadable links found.")

        buttons = []
        caption = "<b>📄 Available Downloads:</b>\n\n"
        all_files = []

        for btn in all_buttons:
            name = btn.text.strip()
            link = "https://megaup.cc" + btn["href"]
            caption += f"• <code>{name}</code>\n"
            buttons.append([InlineKeyboardButton(f"📥 {name}", callback_data=f"wait30|{link}|{name}")])
            all_files.append((link, name))

        # Add Download All
        buttons.append([InlineKeyboardButton("📦 Download All", callback_data=json.dumps({
            "all": True,
            "files": all_files
        }))])

        await message.reply(caption, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await message.reply(f"❌ Error parsing MegaUp link: {e}")


@app.on_callback_query(filters.regex(r"wait30\|"))
async def handle_wait_30(client, query: CallbackQuery):
    _, wait_url, file_name = query.data.split("|", 2)
    msg = await query.message.reply(f"⏳ Waiting 30 seconds for <code>{file_name}</code>...")

    for i in range(30, 0, -5):
        await msg.edit_text(f"⏳ Waiting... {i}s remaining for <code>{file_name}</code>")
        await asyncio.sleep(5)

    await msg.edit_text("🔍 Fetching final download link...")

    # now get the direct download link
    try:
        scraper = cloudscraper.create_scraper()
        html = scraper.get(wait_url).text
        soup = BeautifulSoup(html, "html.parser")
        final_link = soup.find("a", {"id": "downloadButton"})["href"]

        await msg.edit_text("📥 Starting download...")
        await send_downloaded_file(client, query.from_user.id, final_link, file_name)
    except Exception as e:
        await msg.edit(f"❌ Failed to extract final link: {e}")

@app.on_callback_query()
async def handle_callback_json(client, query: CallbackQuery):
    try:
        data = json.loads(query.data)
        if not data.get("all"):
            return

        files = data["files"]
        await query.message.reply(f"📦 Starting download of {len(files)} files...")

        for wait_url, file_name in files:
            msg = await query.message.reply(f"⏳ Starting: {file_name}")
            await asyncio.sleep(30)
            try:
                scraper = cloudscraper.create_scraper()
                html = scraper.get(wait_url).text
                soup = BeautifulSoup(html, "html.parser")
                final_link = soup.find("a", {"id": "downloadButton"})["href"]
                await send_downloaded_file(client, query.from_user.id, final_link, file_name)
                await msg.delete()
            except Exception as e:
                await msg.edit(f"❌ Failed for {file_name}: {e}")
    except:
        pass

# ---------------- UPDATE CMD ---------------- #


@app.on_message(filters.command("update") & filters.user(OWNER_ID))
async def update_bot(client, message):
    msg = await message.reply_text("🔄 Pulling updates from GitHub...")
    try:
        pull = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if pull.returncode == 0:
            await msg.edit(f"✅ Updated:\n<pre>{pull.stdout}</pre>")
        else:
            await msg.edit(f"❌ Git error:\n<pre>{pull.stderr}</pre>")
            return
        await asyncio.sleep(2)
        await msg.edit("♻️ Restarting bot...")
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        await msg.edit(f"⚠️ Error: {e}")

# ---------------- RUN BOT ---------------- #

if __name__ == "__main__":
    app.run()
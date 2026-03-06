from aiohttp import web
import asyncio, os, re
from urllib.parse import urlparse
import math
import tempfile
import zipfile
import shutil
from tqdm.asyncio import tqdm
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import subprocess, sys
import aiohttp
import json
import cloudscraper
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
from config import *  
from database import * 

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
            workers=TG_BOT_WORKERS
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

# -------------- START HANDLER -------------- #
@app.on_message(filters.command('start') & filters.private)
async def start_command(_, message: Message):
    db_pic, db_msg, db_buttons = await db.get_start_config()
    start_text = db_msg if db_msg else START_MSG
    start_photo = db_pic if db_pic else START_PIC

    if db_buttons is not None:
        if db_buttons:
            keyboard_buttons = []
            for row in db_buttons:
                btn_row = []
                for btn in row:
                    if 'url' in btn:
                        btn_row.append(InlineKeyboardButton(text=btn['text'], url=btn['url']))
                    elif 'switch_inline_query_current_chat' in btn:
                        btn_row.append(InlineKeyboardButton(text=btn['text'], switch_inline_query_current_chat=btn['switch_inline_query_current_chat']))
                    elif 'callback_data' in btn:
                        btn_row.append(InlineKeyboardButton(text=btn['text'], callback_data=btn['callback_data']))
                if btn_row:
                    keyboard_buttons.append(btn_row)
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
        else:
            keyboard = None
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔎 Search Manga", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("💻 Contact Developer", url="https://t.me/rohit_1888")]
        ])

    safe_kwargs = {
        "first": message.from_user.first_name or "",
        "last": message.from_user.last_name or "",
        "username": ('@' + message.from_user.username) if message.from_user.username else "",
        "mention": message.from_user.mention,
        "id": message.from_user.id
    }
    
    try:
        caption_text = start_text.format(**safe_kwargs)
    except Exception:
        caption_text = start_text

    await message.reply_photo(
        photo=start_photo,
        caption=caption_text,
        reply_markup=keyboard
    )

# ---------------- SETTINGS CMD ---------------- #
@app.on_message(filters.command("settings") & filters.user(OWNER_ID) & filters.private)
async def settings_command(client: Bot, message: Message):
    db_pic, db_msg, db_buttons = await db.get_start_config()
    current_pic = db_pic if db_pic else START_PIC
    current_msg = db_msg if db_msg else START_MSG
    
    # 1. Ask for Start Picture
    ask_pic_text = (
        "<b>⚙️ Configure Start Picture</b>\n\n"
        "Send the new start picture URL or telegram file ID.\n\n"
        "<b>Current Picture:</b>\n"
        f"<code>{current_pic}</code>\n\n"
        "<i>Send /skip to keep current picture, /cancel to abort.</i>"
    )
    
    try:
        response_pic = await client.ask(chat_id=message.chat.id, text=ask_pic_text, timeout=300)
    except asyncio.TimeoutError:
        return await message.reply_text("⏱️ Timeout! Settings cancelled.")
        
    if response_pic.text and response_pic.text.lower() == "/cancel":
        return await message.reply_text("❌ Cancelled.")
    elif response_pic.text and response_pic.text.lower() == "/skip":
        new_pic = current_pic
    else:
        if response_pic.photo:
            new_pic = response_pic.photo.file_id
        elif response_pic.text:
            new_pic = response_pic.text
        else:
            new_pic = current_pic
    
    # 2. Ask for Start Message
    ask_msg_text = (
        "<b>⚙️ Configure Start Message</b>\n\n"
        "Send the new start message text. Variables:\n"
        "<code>{first}</code>, <code>{last}</code>, <code>{username}</code>, <code>{mention}</code>, <code>{id}</code>\n\n"
        "<b>Current Message:</b>\n"
        f"{current_msg}\n\n"
        "<i>Send /skip to keep current message, /cancel to abort.</i>"
    )
    
    try:
        response1 = await client.ask(chat_id=message.chat.id, text=ask_msg_text, timeout=300)
    except asyncio.TimeoutError:
        return await message.reply_text("⏱️ Timeout! Settings cancelled.")
        
    if response1.text and response1.text.lower() == "/cancel":
        return await message.reply_text("❌ Cancelled.")
    elif response1.text and response1.text.lower() == "/skip":
        new_msg = current_msg
    else:
        new_msg = response1.text if response1.text else current_msg
        
    # 3. Ask for Buttons
    current_buttons_text = ""
    if db_buttons is not None:
        for row in db_buttons:
            row_txt = []
            for btn in row:
                if 'url' in btn:
                    row_txt.append(f"{btn['text']} - {btn['url']}")
                elif 'switch_inline_query_current_chat' in btn:
                    row_txt.append(f"{btn['text']} - inline:{btn['switch_inline_query_current_chat']}")
                elif 'callback_data' in btn:
                    row_txt.append(f"{btn['text']} - callback:{btn['callback_data']}")
            current_buttons_text += " | ".join(row_txt) + "\n"
    else:
        current_buttons_text = "🔎 Search Manga - inline:\n💻 Contact Developer - https://t.me/rohit_1888\n"

    ask_btn_text = (
        "<b>⚙️ Configure Reply Markup Buttons</b>\n\n"
        "Send the buttons in the format: <code>Button Name - url</code>\n"
        "<code>Btn 1 - http://link.com | Btn 2 - inline:</code>\n"
        "<i>Support: url, inline:query, callback:data. Use <code>|</code> to separate buttons on same row.</i>\n\n"
        "<b>Current Buttons:</b>\n"
        f"<code>{current_buttons_text}</code>\n"
        "<i>Send /skip to keep current buttons, /cancel to abort, /none to remove all.</i>"
    )
    
    try:
        response2 = await client.ask(chat_id=message.chat.id, text=ask_btn_text, timeout=300)
    except asyncio.TimeoutError:
        return await message.reply_text("⏱️ Timeout! Settings cancelled.")
        
    if response2.text and response2.text.lower() == "/cancel":
        return await message.reply_text("❌ Cancelled.")
    elif response2.text and response2.text.lower() == "/skip":
        new_buttons = db_buttons # can be None, handled in DB
    elif response2.text and response2.text.lower() == "/none":
        new_buttons = []
    else:
        new_buttons = []
        if response2.text:
            lines = response2.text.strip().split('\n')
            for line in lines:
                if not line.strip(): continue
                row_btns = line.split('|')
                row = []
                for b in row_btns:
                    if '-' not in b: continue
                    parts = b.split('-', 1)
                    t = parts[0].strip()
                    v = parts[1].strip()
                    if v.startswith("inline:"):
                        row.append({"text": t, "switch_inline_query_current_chat": v[7:].strip()})
                    elif v.startswith("callback:"):
                        row.append({"text": t, "callback_data": v[9:].strip()})
                    else:
                        if not (v.startswith("http://") or v.startswith("https://") or v.startswith("t.me/")):
                            v = "https://" + v
                        row.append({"text": t, "url": v})
                if row:
                    new_buttons.append(row)
                
    success = await db.set_start_config(new_pic, new_msg, new_buttons)
    if success:
        await message.reply_text("✅ <b>Settings saved successfully!</b>")
    else:
        await message.reply_text("❌ <b>Failed to save settings. Check logs.</b>")


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
        await msg.edit("♻️ Rᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ...")

        # ✅ Delete after 5s
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

        os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        await msg.edit(f"⚠️ Error: {e}")


BASE_DIR = "/"

@app.on_message(filters.command("list") & filters.user(OWNER_ID))
async def list_agent_fs(_, message: Message):
    try:
        files = sorted(os.listdir("/"))

        text = "📁 <b>Agent Filesystem (/)</b>\n\n"

        for f in files:
            path = os.path.join("/", f)
            if os.path.isdir(path):
                text += f"📂 <code>{f}/</code>\n"
            else:
                try:
                    size = os.path.getsize(path) // 1024
                    text += f"📄 <code>{f}</code> ({size} KB)\n"
                except:
                    text += f"📄 <code>{f}</code>\n"

        await message.reply_text(text)

    except Exception as e:
        await message.reply_text(f"❌ Error:\n<pre>{e}</pre>")

@app.on_message(filters.command("get") & filters.user(OWNER_ID))
async def get_agent_file(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❗ Usage:\n<code>/get path</code>\nExample: <code>/get /app</code>")

    path = message.command[1]

    if not os.path.exists(path):
        return await message.reply_text("❌ Path not found")

    msg = await message.reply_text("📦 Zipping agent files...")

    import zipfile, tempfile

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            zip_path = tmp.name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isfile(path):
                zipf.write(path, arcname=os.path.basename(path))
            else:
                for root, _, files in os.walk(path):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = full.lstrip("/")
                        zipf.write(full, arc)

        await message.reply_document(
            zip_path,
            caption=f"📦 Agent files: <code>{path}</code>"
        )

        os.remove(zip_path)
        await msg.delete()

    except Exception as e:
        await msg.edit(f"❌ Error:\n<pre>{e}</pre>")

# ---------------- RUN BOT ---------------- #
if __name__ == "__main__":
    app.run()
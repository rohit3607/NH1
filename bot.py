from aiohttp import web
import asyncio, os, re, fitz, requests
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

# -------------- INLINE SEARCH -------------- #
@app.on_inline_query()
async def inline_search(client: Client, inline_query):
    query = inline_query.query.strip()
    page = int(inline_query.offset) if inline_query.offset else 1

    results = await search_nhentai(query or None, page)
    next_offset = str(page + 1) if len(results) == 10 else ""
    await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)


# ---------------- INLINE SEARCH ---------------- #
async def search_nhentai(query=None, page=1):
    results = []
    scraper = cloudscraper.create_scraper() 

    if query:
        url = f"https://nhentai.net/search/?q={query.replace(' ', '+')}&page={page}"
    else:
        url = f"https://nhentai.net/?page={page}"

    html = scraper.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    gallery_items = soup.select(".gallery")

    for item in gallery_items[:10]:
        link = item.select_one("a.cover")["href"]
        code = link.split("/")[2]
        title = item.select_one(".caption").text.strip() if item.select_one(".caption") else f"Code {code}"

        img_tag = item.select_one("img")
        thumb = img_tag.get("data-src") or img_tag.get("src")
        if thumb and thumb.startswith("//"):
            thumb = "https:" + thumb

        results.append(
            InlineQueryResultArticle(
                title=title,
                description=f"Code: {code}",
                thumb_url=thumb,
                input_message_content=InputTextMessageContent(
                    message_text=f"**{title}**\n🔗 [Read Now](https://nhentai.net/g/{code}/)\n\n`Code:` {code}",
                    disable_web_page_preview=True
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download PDF", callback_data=f"download_{code}")]
                ])
            )
        )
    return results

# ------------ PAGE DOWNLOADER -------------- #
async def download_page(session, url, filename):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to download: {url}")
        with open(filename, "wb") as f:
            f.write(await resp.read())

# -------------- PDF GENERATOR -------------- #

async def download_manga_as_pdf(code: str, progress_callback=None):
    pdf_path = f"{code}.pdf"
    thumb_path = f"{code}_thumb.jpg"

    try:
        if progress_callback:
            await progress_callback(0, 100, "🔍 Fetching pages")

        # ✅ Get gallery info
        url = f"https://nhentai.net/g/{code}/"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            raise Exception(f"Failed to fetch gallery page: {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")
        img_tags = soup.select("#thumbnail-container img")

        if not img_tags:
            raise Exception("No pages found for this code!")

        img_urls = []
        for img in img_tags:
            src = img.get("data-src") or img.get("src")
            if src.startswith("//"):
                src = "https:" + src
            img_urls.append(src.replace("t.nhentai.net", "i.nhentai.net").replace("t.jpg", ".jpg"))

        total = len(img_urls)

        # ✅ Build PDF
        doc = fitz.open()
        for i, img_url in enumerate(img_urls, 1):
            r = requests.get(img_url, headers={"User-Agent": "Mozilla/5.0"})
            img = Image.open(BytesIO(r.content)).convert("RGB")

            rect = fitz.Rect(0, 0, img.width, img.height)
            page = doc.new_page(width=img.width, height=img.height)
            pix = fitz.Pixmap(fitz.csRGB, img.width, img.height, img.tobytes())
            page.insert_image(rect, stream=r.content)

            if i == 1:  # save first page as thumb
                img.save(thumb_path, "JPEG")

            if progress_callback:
                await progress_callback(i, total, "📖 Downloading")

        doc.save(pdf_path)
        doc.close()

        return pdf_path, thumb_path

    except Exception as e:
        raise Exception(f"Download failed: {e}")

# ------------ CALLBACK HANDLER ------------- #

@app.on_callback_query(filters.regex(r"^download_(\d+)$"))
async def handle_download(client: Client, callback: CallbackQuery):
    code = callback.matches[0].group(1)

    # ⚡ Always answer callback (important!)
    try:
        await callback.answer("⏳ Fetching manga...", show_alert=False)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await callback.answer("⏳ Fetching manga...", show_alert=False)

    pdf_path = thumb_path = None
    msg = None

    try:
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        try:
            msg = await callback.message.reply("📥 Starting download...")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msg = await callback.message.reply("📥 Starting download...")

        # Progress callback
        async def progress(cur, total, stage):
            percent = int((cur / total) * 100)
            txt = f"{stage}... {percent}%"
            try:
                await msg.edit(txt)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await msg.edit(txt)
            except:
                pass

        # ✅ Download PDF
        pdf_path, thumb_path = await download_manga_as_pdf(code, progress)

        try:
            await msg.edit("📤 Uploading PDF...")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await msg.edit("📤 Uploading PDF...")

        # Upload progress callback
        async def upload_progress(cur, total):
            percent = int((cur / total) * 100)
            try:
                await msg.edit(f"📤 Uploading... {percent}%")
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await msg.edit(f"📤 Uploading... {percent}%")
            except:
                pass

        # ✅ Upload to user
        try:
            await client.send_document(
                chat_id,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
                progress=upload_progress
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.send_document(
                chat_id,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
                progress=upload_progress
            )

        # ✅ Upload to your log/channel
        try:
            await client.send_document(
                -1002805198226,  # your log channel
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.send_document(
                -1002805198226,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}"
            )

        try:
            await msg.edit("✅ Done!")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await msg.edit("✅ Done!")

    except Exception as e:
        try:
            await msg.edit(f"❌ Error: {e}")
        except FloodWait as e2:
            await asyncio.sleep(e2.value)
            await msg.edit(f"❌ Error: {e}")
        except:
            pass
    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

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
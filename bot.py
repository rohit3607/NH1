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
import aiohttp, aiofiles
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
            workers=50
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
    scraper = cloudscraper.create_scraper()  # ✅ bypass Cloudflare

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
                    disable_web_page_preview=False
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download PDF", callback_data=f"download_{code}")]
                ])
            )
        )
    return results


# =============== GENERATE THUMBNAIL ================= #
async def generate_thumbnail(image_path, thumb_path):
    img = Image.open(image_path)
    img.thumbnail((320, 320))
    img.save(thumb_path, "JPEG")
    return thumb_path


# =============== PAGE DOWNLOADER ================= #
async def download_page(session, url, filename):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to download: {url}")
        data = await resp.read()
        async with aiofiles.open(filename, "wb") as f:
            await f.write(data)


# =============== MANGA TO PDF ================= #
async def download_manga_as_pdf(code, progress_callback=None):
    scraper = cloudscraper.create_scraper()
    api_url = f"https://nhentai.net/api/gallery/{code}"
    resp = scraper.get(api_url)

    if resp.status_code != 200:
        raise Exception("Gallery not found.")
    data = resp.json()

    folder = f"nhentai_{code}"
    os.makedirs(folder, exist_ok=True)

    num_pages = len(data["images"]["pages"])
    ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
    media_id = data["media_id"]
    image_paths = []

    async with aiohttp.ClientSession() as session:
        for i, page in enumerate(data["images"]["pages"], start=1):
            ext = ext_map.get(page["t"], "jpg")
            url = f"https://i.nhentai.net/galleries/{media_id}/{i}.{ext}"
            path = os.path.join(folder, f"{i:03}.{ext}")
            await download_page(session, url, path)
            image_paths.append(path)

            if progress_callback:
                await progress_callback(i, num_pages, "Downloading")

    # Generate PDF
    pdf_path = f"{folder}.pdf"
    first_img = Image.open(image_paths[0]).convert("RGB")
    first_img.save(
        pdf_path,
        format="PDF",
        save_all=True,
        append_images=[Image.open(p).convert("RGB") for p in image_paths[1:]]
    )

    # Thumbnail
    thumb_path = f"{folder}_thumb.jpg"
    await generate_thumbnail(image_paths[0], thumb_path)

    # Cleanup images
    for img in image_paths:
        os.remove(img)
    os.rmdir(folder)

    return pdf_path, thumb_path


# =============== CALLBACK HANDLER ================= #
@Client.on_callback_query(filters.regex(r"^download_(\d+)$"))
async def handle_download(client: Client, callback: CallbackQuery):
    code = callback.matches[0].group(1)
    pdf_path = None
    thumb_path = None
    msg = None

    try:
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        if callback.message:
            msg = await callback.message.reply("📥 Starting download...")
        else:
            await callback.answer("📥 Starting download...")

        # Progress function
        async def progress(cur, total, stage="Downloading"):
            if total == 0:
                return
            percent = int((cur / total) * 100)
            txt = f"{stage}... {percent}%"
            try:
                if msg:
                    await msg.edit(txt)
            except:
                pass

        # Download manga as PDF
        pdf_path, thumb_path = await download_manga_as_pdf(code, progress)

        if msg:
            await msg.edit("📤 Uploading PDF...")

        # Upload to user
        try:
            await client.send_document(
                chat_id,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
                progress=progress,
                progress_args=("Uploading",)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.send_document(
                chat_id,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
                progress=progress,
                progress_args=("Uploading",)
            )

        # Upload to channel
        try:
            await client.send_document(
                -1002805198226,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.send_document(
                -1002805198226,
                document=pdf_path,
                thumb=thumb_path,
                caption=f"📖 Manga: {code}",
            )

        # ✅ Delete progress message
        if msg:
            await msg.delete()

    except Exception as e:
        err = f"❌ Error: {e}"
        try:
            if msg:
                await msg.edit(err)
            else:
                await callback.edit_message_text(err)
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
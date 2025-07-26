from aiohttp import web
import asyncio, os, re
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import subprocess, sys
import cloudscraper
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
@app.on_inline_query()
async def inline_search(client: Client, inline_query):
    query = inline_query.query.strip()
    page = int(inline_query.offset) if inline_query.offset else 1

    results = await search_nhentai(query or None, page)
    next_offset = str(page + 1) if len(results) == 10 else ""
    await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)

async def search_nhentai(query=None, page=1):
    results = []
    url = f"https://nhentai.net/search/?q={query.replace(' ', '+')}&page={page}" if query else f"https://nhentai.net/?page={page}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    gallery_items = soup.select(".gallery")

    for item in gallery_items[:10]:
        link = item.select_one("a")["href"]
        code = link.split("/")[2]
        title = item.select_one(".caption").text.strip() if item.select_one(".caption") else f"Code {code}"
        thumb = item.select_one("img").get("data-src") or item.select_one("img").get("src")
        if thumb.startswith("//"):
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

# ---------------- PAGE DOWNLOADER ---------------- #
async def download_page(session, url, filename):
    headers = {"User-Agent": "Mozilla/5.0"}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"Failed to download: {url}")
        with open(filename, "wb") as f:
            f.write(await resp.read())

# ---------------- PDF GENERATOR ---------------- #
async def download_manga_as_pdf(code, progress_callback=None):
    api_url = f"https://nhentai.net/api/gallery/{code}"
    folder = f"nhentai_{code}"
    os.makedirs(folder, exist_ok=True)

    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as resp:
            if resp.status != 200:
                raise Exception("Gallery not found.")
            data = await resp.json()

        num_pages = len(data["images"]["pages"])
        ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
        media_id = data["media_id"]
        image_paths = []

        for i, page in enumerate(data["images"]["pages"], start=1):
            ext = ext_map.get(page["t"], "jpg")
            url = f"https://i.nhentai.net/galleries/{media_id}/{i}.{ext}"
            path = os.path.join(folder, f"{i:03}.{ext}")
            await download_page(session, url, path)
            image_paths.append(path)
            if progress_callback:
                await progress_callback(i, num_pages, "Downloading")

    # Generate PDF without loading all images in memory
    pdf_path = f"{folder}.pdf"
    first_img = Image.open(image_paths[0]).convert("RGB")
    with open(pdf_path, "wb") as f:
        first_img.save(f, format="PDF", save_all=True, append_images=[
            Image.open(p).convert("RGB") for p in image_paths[1:]
        ])

    for img in image_paths:
        os.remove(img)
    os.rmdir(folder)
    return pdf_path

# ---------------- CALLBACK HANDLER ---------------- #
@app.on_callback_query(filters.regex(r"^download_(\d+)$"))
async def handle_download(client: Client, callback: CallbackQuery):
    code = callback.matches[0].group(1)
    pdf_path = None
    msg = None  # <== FIX: define msg early to avoid UnboundLocalError

    try:
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        if callback.message:
            msg = await callback.message.reply("📥 Starting download...")
        else:
            await callback.answer("📥 Starting download...")

        async def progress(cur, total, stage):
            percent = int((cur / total) * 100)
            txt = f"{stage}... {percent}%"
            try:
                if msg:
                    await msg.edit(txt)
                else:
                    await callback.edit_message_text(txt)
            except:
                pass

        pdf_path = await download_manga_as_pdf(code, progress)

        if msg:
            await msg.edit("📤 Uploading PDF...")
        else:
            await callback.edit_message_text("📤 Uploading PDF...")

        await client.send_document(chat_id, document=pdf_path, caption=f"📖 Manga: {code}")

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


user_file_cache = {}

# 🧠 Format size in human-readable form
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G"]:
        if abs(num) < 1024:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024
    return f"{num:.1f}T{suffix}"

# ⬇️ Parse file qualities and sizes
async def parse_megaup_links(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res:
            html = await res.text()

    soup = BeautifulSoup(html, "html.parser")
    script_text = soup.find("script", text=re.compile("sources")).text
    files = re.findall(r'\{file:"(.*?)",label:"(.*?)"\}', script_text)

    result = []
    async with aiohttp.ClientSession() as session:
        for file_url, label in files:
            async with session.head(file_url) as r:
                size = int(r.headers.get("Content-Length", 0))
                result.append((file_url, label, size))
    return result

# ⬇️ Progress updater
async def progress(current, total, message, prefix="Uploading"):
    percentage = current * 100 / total
    bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
    try:
        await message.edit_text(
            f"{prefix}...\n[{bar}] {percentage:.2f}%\n{sizeof_fmt(current)} / {sizeof_fmt(total)}"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)

# ⬇️ Download file with progress
async def download_with_progress(url, label, temp_msg):
    filename = f"/tmp/{label.replace(' ', '_')}.mp4"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                total = int(res.headers.get('Content-Length', 0))
                downloaded = 0
                with open(filename, "wb") as f:
                    async for chunk in res.content.iter_chunked(1024 * 512):
                        f.write(chunk)
                        downloaded += len(chunk)
                        await progress(downloaded, total, temp_msg, prefix="Downloading")
        return filename
    except Exception as e:
        await temp_msg.edit_text(f"❌ Failed to download: {e}")
        return None

# ⬆️ Upload with progress
async def upload_with_progress(client, message, file_path, label):
    total = os.path.getsize(file_path)
    sent_msg = await message.reply("📤 Starting upload...")

    async def update(current, total):
        await progress(current, total, sent_msg, prefix="Uploading")

    await client.send_document(
        message.chat.id,
        document=file_path,
        file_name=os.path.basename(file_path),
        caption=f"🎬 {label}",
        progress=update,
        progress_args=(total,),
    )
    await sent_msg.delete()

# 📥 Trigger download after 30s and send
async def download_and_send(client, message, url, label):
    await message.reply(f"⏳ Waiting 30s before downloading **{label}**...")
    await asyncio.sleep(30)

    progress_msg = await message.reply("🔁 Initializing download...")
    file_path = await download_with_progress(url, label, progress_msg)

    if file_path:
        await upload_with_progress(client, message, file_path, label)
        os.remove(file_path)

# 🧠 /dl command handler
@app.on_message(filters.command("dl") & filters.private)
async def handle_dl(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Usage: `/dl <MegaUp link>`")

    url = message.command[1]
    if "megaup.cc" not in url:
        return await message.reply("❌ Invalid MegaUp link.")

    try:
        files = await parse_megaup_links(url)
        if not files:
            return await message.reply("❌ No downloadable files found.")

        user_file_cache[message.from_user.id] = files

        buttons = [
            [InlineKeyboardButton(f"📥 {label} ({sizeof_fmt(size)})", callback_data=f"dl_{i}")]
            for i, (_, label, size) in enumerate(files)
        ]
        buttons.append([InlineKeyboardButton("📦 Download All", callback_data="dl_all")])

        await message.reply("🎬 Choose quality to download:", reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# 🧠 Handle button clicks
@app.on_callback_query(filters.regex(r"^dl_"))
async def handle_button(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    if user_id not in user_file_cache:
        return await callback.answer("⚠️ Session expired. Please try again.", show_alert=True)

    files = user_file_cache[user_id]
    await callback.answer()

    if data == "dl_all":
        for url, label, _ in files:
            await download_and_send(client, callback.message, url, label)
    else:
        index = int(data.replace("dl_", ""))
        if index >= len(files):
            return await callback.message.reply("❌ Invalid selection.")

        url, label, _ = files[index]
        await download_and_send(client, callback.message, url, label)

# ---------------- RUN BOT ---------------- #

if __name__ == "__main__":
    app.run()
from aiohttp import web
import asyncio, os, re, shutil
from urllib.parse import urlparse
import math
import tempfile
#from tqdm import tqdm
from tqdm.asyncio import tqdm
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import subprocess, sys, fitz
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 Search (.net)", switch_inline_query_current_chat="net ")],
        [InlineKeyboardButton("🔎 Search (.to)", switch_inline_query_current_chat="to ")],
        [InlineKeyboardButton("🔎 Search (.xxx)", switch_inline_query_current_chat="xxx ")],
        [InlineKeyboardButton("🦊 Search (hentaifox)", switch_inline_query_current_chat="fox ")],
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

# -------------- URL HANDLER -------------- #
@app.on_message(filters.regex(r"https?://(nhentai\.(net|to|xxx)|hentaifox\.com)/(g|gallery)/(\d+)/?") & filters.private)
async def handle_url(client: Client, message: Message):
    site_domain = message.matches[0].group(1)
    site = "fox" if "hentaifox" in site_domain else site_domain.split(".")[-1]
    code = message.matches[0].group(4)
    
    await message.reply(
        f"**Detected Link:** `{code}` from `{site_domain}`\n\nClick below to download as PDF.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download PDF", callback_data=f"download_{site}_{code}")]
        ])
    )

# -------------- INLINE SEARCH -------------- #
@app.on_inline_query()
async def inline_search(client: Client, inline_query):
    query = inline_query.query.strip()
    page = int(inline_query.offset) if inline_query.offset else 1

    site = "net"
    search_query = query
    if query:
        parts = query.split(" ", 1)
        if parts[0].lower() in ["net", "to", "xxx", "fox"]:
            site = parts[0].lower()
            search_query = parts[1] if len(parts) > 1 else ""

    results = await search_nhentai(search_query or None, page, site)
    next_offset = str(page + 1) if len(results) == 10 else ""
    await inline_query.answer(results, cache_time=1, is_personal=True, next_offset=next_offset)


# -------------- INLINE SEARCH -------------- #
async def search_nhentai(query=None, page=1, site="net"):
    results = []
    scraper = cloudscraper.create_scraper()
    
    domains = {
        "net": "nhentai.net",
        "to": "nhentai.to",
        "xxx": "nhentai.xxx",
        "fox": "hentaifox.com"
    }
    domain = domains.get(site, "nhentai.net")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://{domain}/"
    }

    if site == "fox":
        if query:
            url = f"https://{domain}/search/?q={query.replace(' ', '+')}&page={page}"
        else:
            url = f"https://{domain}/pag/{page}/" if page > 1 else f"https://{domain}/"
    elif query:
        url = f"https://{domain}/search?q={query.replace(' ', '+')}&page={page}"
    else:
        # No query – show home page results
        if site == "to":
            # nhentai.to uses /go for the main gallery feed
            url = f"https://{domain}/go?page={page}"
        else:
            url = f"https://{domain}/?page={page}"

    try:
        resp = scraper.get(url, headers=headers)
        # If primary request fails (e.g., 403), try fallback domains
        if resp.status_code != 200:
            for fb_site, fb_domain in domains.items():
                if fb_site == site:
                    continue
                # Build fallback URL using same logic as above
                if query:
                    fb_url = f"https://{fb_domain}/search?q={query.replace(' ', '+')}&page={page}"
                else:
                    if fb_site == "to":
                        fb_url = f"https://{fb_domain}/go?page={page}"
                    else:
                        fb_url = f"https://{fb_domain}/?page={page}"
                fb_resp = scraper.get(fb_url, headers=headers)
                if fb_resp.status_code == 200:
                    resp = fb_resp
                    print(f"Search fallback to [{fb_site}] succeeded.")
                    break
        print(f"Search [{site}] Status: {resp.status_code}")
        html = resp.text
    except Exception as e:
        print(f"Search Error: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    # Expand selector to capture more gallery entries across sites
    gallery_items = soup.select(
        ".gallery, .gallery-item, .gallery_item, .item, .thumb, .gallery .cover, .gallery .inner_thumb, .gallery .thumb"
    )

    for item in gallery_items[:10]:
        try:
            # Flexible link extraction
            link_tag = item.select_one(".inner_thumb a") or item.select_one(".caption a") or item.select_one("a.cover") or item.select_one("a")
            if not link_tag or not link_tag.has_attr("href"): continue
            
            link = link_tag["href"]
            code = link.strip("/").split("/")[-1]
            
            # Flexible title extraction
            title_tag = item.select_one(".g_title") or item.select_one(".caption") or item.select_one(".title") or item.select_one(".name")
            title = title_tag.text.strip() if title_tag else f"Code {code}"

            # Flexible image extraction
            img_tag = item.select_one(".inner_thumb img") or item.select_one("img")
            if not img_tag: continue
            
            thumb = img_tag.get("data-src") or img_tag.get("src")
            if thumb and thumb.startswith("//"):
                thumb = "https:" + thumb

            read_url = f"https://{domain}/gallery/{code}/" if site == "fox" else f"https://{domain}/g/{code}/"

            results.append(
                InlineQueryResultArticle(
                    title=f"[{site.upper()}] {title}",
                    description=f"Code: {code} | Site: {domain}",
                    thumbnail_url=thumb,
                    input_message_content=InputTextMessageContent(
                        message_text=f"**{title}**\n🔗 [Read on {domain}]({read_url})\n\n`Code:` {code}\n`Site:` {site}",
                        disable_web_page_preview=False
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📥 Download PDF", callback_data=f"download_{site}_{code}")]
                    ])
                )
            )
        except:
            continue
    return results


async def download_image(session, url, path):
    for _ in range(3):
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
                    return True
        except:
            await asyncio.sleep(1)
    return False

# -------------- PDF GENERATOR -------------- #
async def download_manga_as_pdf(code, site="net", progress_callback=None):
    scraper = cloudscraper.create_scraper()
    
    domains = {
        "net": "nhentai.net",
        "to": "nhentai.to",
        "xxx": "nhentai.xxx",
        "fox": "hentaifox.com"
    }
    domain = domains.get(site, "nhentai.net")
    gallery_url = f"https://{domain}/gallery/{code}/" if site == "fox" else f"https://{domain}/g/{code}/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": gallery_url
    }

    # -------- FETCH METADATA (API v2) -------- #
    api_success = False
    media_id = None
    images = []
    if site == "net":
        try:
            api_resp = scraper.get(f"https://nhentai.net/api/v2/galleries/{code}", headers=headers, timeout=10)
            if api_resp.status_code == 200:
                data = api_resp.json()
                media_id = str(data.get("media_id"))
                pages = data.get("pages", [])
                for p in pages:
                    path = p.get("path")
                    if path:
                        images.append(path.split(".")[-1])
                    else:
                        ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
                        images.append(ext_map.get(p.get("t"), "jpg"))
                api_success = True
        except Exception as e:
            print(f"API v2 error: {e}")
    if not api_success:
        # Fallback to HTML scraping
        try:
            resp = scraper.get(gallery_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                raise Exception(f"Gallery not found on {domain} ({resp.status_code})")
            html = resp.text
        except Exception as e:
            raise Exception(f"Connection Error on {domain}: {e}")
        soup = BeautifulSoup(html, "html.parser")

    
    if not api_success:
        # -------- EXTRACT METADATA -------- #
        media_id = None
        images = []
        # 1. Try modern nhentai embedded script JSON
        for s in soup.find_all("script"):
            txt = ''.join(s.find_all(string=True))
            if 'media_id' in txt:
                try:
                    data = json.loads(txt)
                    body = json.loads(data['body']) if (isinstance(data, dict) and 'body' in data and isinstance(data['body'], str)) else data
                    if isinstance(body, dict) and 'media_id' in body:
                        media_id = str(body['media_id'])
                        # Check body['pages']
                        if 'pages' in body and isinstance(body['pages'], list):
                            for p in body['pages']:
                                if isinstance(p, dict) and 'path' in p:
                                    images.append(p['path'].split('.')[-1])
                                elif isinstance(p, dict) and 't' in p:
                                    ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
                                    images.append(ext_map.get(p["t"], "jpg"))
                        elif 'images' in body and isinstance(body['images'], dict) and 'pages' in body['images']:
                            for img in body['images']['pages']:
                                ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
                                images.append(ext_map.get(img["t"], "jpg"))
                        if media_id and images:
                            break
                except Exception:
                    pass
    else:
        # API already provided media_id and images
        pass

    # 2. Try legacy JSON extraction (window._gallery = JSON.parse("..."))
    if not media_id or not images:
        json_match = re.search(r'window\._gallery\s*=\s*JSON\.parse\("(.*?)"\);', html)
        if json_match:
            try:
                raw_json = json_match.group(1).encode('utf-8').decode('unicode_escape')
                gallery_data = json.loads(raw_json)
                media_id = str(gallery_data.get("media_id"))
                for img in gallery_data.get("images", {}).get("pages", []):
                    ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
                    images.append(ext_map.get(img["t"], "jpg"))
            except Exception as e:
                print(f"JSON Parse Error: {e}")

    # 3. Try legacy simple JSON extraction (window._gallery = {...})
    if not media_id or not images:
        json_match = re.search(r'window\._gallery\s*=\s*({.*?});', html, re.S)
        if json_match:
            try:
                gallery_data = json.loads(json_match.group(1))
                media_id = str(gallery_data.get("media_id"))
                for img in gallery_data.get("images", {}).get("pages", []):
                    ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
                    images.append(ext_map.get(img["t"], "jpg"))
            except:
                pass

    # 4. Fallback: Scrape from page structure (for nhentai.to and others)
    img_domain_override = None
    if not media_id or not images:
        # Priority 1: Check cover image or first thumbnail (most reliable for MediaID)
        cover_img = soup.select_one("#cover img, .cover img, .gallery_cover img, .gallery_top img, .gallerythumb img, .thumb-container img")
        if cover_img:
            src = cover_img.get("data-src") or cover_img.get("src") or ""
            # Standard MediaID pattern
            match = re.search(r'/galleries/(\d+)/', src)
            if match:
                media_id = match.group(1)
            else:
                # Mirror pattern (e.g. nhentai.xxx or hentaifox.com)
                match = re.search(r'nhentaimg\.com/(\d+/[a-zA-Z0-9]+)', src) or re.search(r'hentaifox\.com/(\d+/\d+)', src)
                if match:
                    media_id = match.group(1)
                    img_domain_override = re.search(r'(https?://[^/]+)', src).group(1)
        
        # Priority 2: Find media_id from ANY gallery link/img if cover failed
        if not media_id:
            for attr in ["src", "data-src", "href"]:
                tags = soup.find_all(lambda t: t.has_attr(attr) and ("/galleries/" in t[attr] or "nhentaimg.com" in t[attr] or "hentaifox.com" in t[attr]))
                for tag in tags:
                    val = tag[attr]
                    match = re.search(r'/galleries/(\d+)/', val)
                    if not match:
                        match = re.search(r'nhentaimg\.com/(\d+/[a-zA-Z0-9]+)', val) or re.search(r'hentaifox\.com/(\d+/\d+)', val)
                        if match:
                            img_domain_override = re.search(r'(https?://[^/]+)', val).group(1)
                    
                    if match:
                        media_id = match.group(1)
                        break
                if media_id: break
        
        # Count pages from total pages text (e.g. "Pages: 25" or "25 pages")
        stats = soup.select_one("#tags, .tag-container, #info, .info, .gallery_right, span.pages")
        total_pages = None
        if stats:
            pages_text = re.search(r'Pages:\s*(\d+)', stats.text, re.I) or re.search(r'(\d+)\s+pages', stats.text, re.I)
            if pages_text:
                total_pages = int(pages_text.group(1))

        if not total_pages:
            pages_el = soup.select_one('.tag_name.pages, span.pages')
            if pages_el and pages_el.text.strip().isdigit():
                total_pages = int(pages_el.text.strip())

        if total_pages:
            # Fallback extensions: detect from thumbnails
            detected_ext = "jpg"
            thumbs = soup.select(".gallerythumb img, .thumb-container img, .gt_th img")
            for thumb in thumbs[:10]:
                src = thumb.get("data-src") or thumb.get("src") or ""
                if ".webp" in src:
                    detected_ext = "webp"
                    break
                elif ".png" in src:
                    detected_ext = "png"
                    break
            images = [detected_ext] * total_pages
        else:
            # Last resort: count thumbnails without duplicating nested elements
            thumbs = soup.select(".thumb-container") or soup.select(".gallerythumb") or soup.select(".gt_th")
            if thumbs:
                total_pages = len(thumbs)
                images = ["jpg"] * total_pages

    if not media_id:
        # Last ditch effort for media_id from HTML source
        match = re.search(r'/galleries/(\d+)/', html)
        if not match:
            match = re.search(r'nhentaimg\.com/(\d+/[a-zA-Z0-9]+)', html) or re.search(r'hentaifox\.com/(\d+/\d+)', html)
        if match: media_id = match.group(1)

    if not media_id or not images:
        raise Exception(f"Could not extract gallery metadata from {domain}. MediaID: {media_id}, Pages: {len(images)}")

    # -------- IMAGE SERVERS -------- #
    img_domains = {
        "net": "i.nhentai.net",
        "to": "zrocdn.xyz",
        "xxx": "i5.nhentaimg.com",
        "fox": "i3.hentaifox.com"
    }
    img_domain = img_domains.get(site, "i.nhentai.net")

    folder = f"{site}_{code}"
    os.makedirs(folder, exist_ok=True)
    
    total_pages = len(images)
    
    # -------- DOWNLOAD IMAGES -------- #
    async with aiohttp.ClientSession(headers=headers) as session:
        # Auto-detect real extension (mirrors like .xxx often use webp instead of jpg)
        real_ext = images[0]
        test_pg = 1
        for ext_test in [real_ext, "webp", "jpg", "png"]:
            if img_domain_override:
                test_url = f"{img_domain_override}/{media_id}/{test_pg}.{ext_test}"
            elif site == "xxx":
                test_url = f"https://i5.nhentaimg.com/{media_id}/{test_pg}.{ext_test}"
            elif site == "fox":
                test_url = f"https://i3.hentaifox.com/{media_id}/{test_pg}.{ext_test}"
            else:
                test_url = f"https://{img_domain}/galleries/{media_id}/{test_pg}.{ext_test}"
            
            try:
                async with session.get(test_url, timeout=10) as resp:
                    if resp.status == 200:
                        real_ext = ext_test
                        break
            except: continue

        if real_ext and images and real_ext != images[0]:
            images = [real_ext] * total_pages

        for i in range(0, total_pages, 10): # Batch of 10
            batch_tasks = []
            for j in range(i, min(i + 10, total_pages)):
                ext = images[j] if j < len(images) else real_ext
                pg = j + 1
                
                # Dynamic URL building
                if img_domain_override:
                    img_url = f"{img_domain_override}/{media_id}/{pg}.{ext}"
                elif site == "xxx":
                    img_url = f"https://i5.nhentaimg.com/{media_id}/{pg}.{ext}"
                elif site == "fox":
                    img_url = f"https://i3.hentaifox.com/{media_id}/{pg}.{ext}"
                else:
                    img_url = f"https://{img_domain}/galleries/{media_id}/{pg}.{ext}"
                
                img_path = os.path.join(folder, f"{pg:03d}.{ext}")
                batch_tasks.append(download_image(session, img_url, img_path))
            
            await asyncio.gather(*batch_tasks)
            if progress_callback:
                await progress_callback(min(i + 10, total_pages), total_pages)

    # -------- LOAD IMAGES -------- #
    image_files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ])

    if not image_files:
        raise Exception("No images downloaded successfully")

    # -------- CREATE PDF -------- #
    pdf_path = f"{folder}.pdf"
    doc = fitz.open()

    for img_path in image_files:
        try:
            # Try to open image with fitz directly (works for JPG, PNG)
            try:
                img_doc = fitz.open(img_path)
            except:
                # Fallback for WebP or other formats fitz might not handle directly
                img = Image.open(img_path).convert("RGB")
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_doc = fitz.open("jpeg", img_byte_arr.getvalue())

            # Convert image to PDF bytes
            pdfbytes = img_doc.convert_to_pdf()
            img_doc.close()
            # Open the PDF bytes as a new document and insert into main doc
            img_pdf = fitz.open("pdf", pdfbytes)
            doc.insert_pdf(img_pdf)
            img_pdf.close()
        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
            continue

    if len(doc) == 0:
        doc.close()
        raise Exception("Failed to process images for PDF (all frames failed)")

    doc.save(pdf_path)
    doc.close()

    # -------- CLEANUP -------- #
    try:
        shutil.rmtree(folder)
    except:
        pass

    return pdf_path

# ------------ CALLBACK HANDLER ------------- #
@app.on_callback_query(filters.regex(r"^download_(net|to|xxx|fox)_(\d+)$"))
async def handle_download(client: Client, callback: CallbackQuery):
    site = callback.matches[0].group(1)
    code = callback.matches[0].group(2)
    pdf_path, msg, sent_msg = None, None, None

    try:
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        if callback.message:
            msg = await callback.message.reply("📥 Sᴛᴀʀᴛɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...")
        else:
            await callback.answer("📥 Sᴛᴀʀᴛɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...")

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

        # Download PDF
        async def dl_progress(cur, total):
            await progress(cur, total, "📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ")

        pdf_path = await download_manga_as_pdf(code, site, dl_progress)

        if msg:
            await msg.edit("📤 Uᴘʟᴏᴀᴅɪɴɢ PDF... 0%")
        else:
            await callback.edit_message_text("📤 Uᴘʟᴏᴀᴅɪɴɢ PDF... 0%")

        # Upload with progress
        async def upload_progress(cur, total):
            await progress(cur, total, "📤 Uᴘʟᴏᴀᴅɪɴɢ")

        try:
            sent_msg = await client.send_document(
                chat_id,
                document=pdf_path,
                caption=f"📖 Manga: {code}",
                progress=upload_progress
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            sent_msg = await client.send_document(
                chat_id,
                document=pdf_path,
                caption=f"📖 Manga: {code}",
                progress=upload_progress
            )

        # Copy uploaded message to channel (no second upload)
        try:
            await client.copy_message(
                chat_id=LOG_CHANNEL,
                from_chat_id=chat_id,
                message_id=sent_msg.id
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.copy_message(
                chat_id=LOG_CHANNEL,
                from_chat_id=chat_id,
                message_id=sent_msg.id
            )

        if msg:
            await msg.delete()
        elif callback.message:
            try:
                await callback.message.delete()
            except:
                pass

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

# ---------------- RUN BOT ---------------- #
if __name__ == "__main__":
    app.run()
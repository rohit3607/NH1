from aiohttp import web
import asyncio, os, re
import tempfile
from datetime import datetime
import subprocess, sys
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
from faster_whisper import WhisperModel
import math

# ---------------- CONFIG ---------------- #
from config import *  
from database import * 

# ---------------- WEB SERVER ---------------- #
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_handler(request):
    return web.json_response("Subtitle Generator Bot Running")

async def web_server():
    web_app = web.Application(client_max_size=9000000000)
    web_app.add_routes(routes)
    return web_app

# ---------------- QUEUE SYSTEM ---------------- #
queue = asyncio.Queue()
active_tasks = 0

async def format_time(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02},000"

# Progress bar formatting
def create_progress_bar(current, total, length=20):
    if total == 0:
        return "[--------------------]"
    percentage = current / total
    filled_length = int(length * percentage)
    bar = "█" * filled_length + "-" * (length - filled_length)
    return f"[{bar}] {percentage * 100:.1f}%"

def get_readable_size(size_in_bytes):
    if not size_in_bytes:
        return '0 B'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit = 0
    while size_in_bytes >= 1024 and unit < len(units) - 1:
        size_in_bytes /= 1024.0
        unit += 1
    return f"{size_in_bytes:.2f} {units[unit]}"

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time()
    diff = now - start
    if round(diff % 5.0) == 0 or current == total:
        percentage = current * 100 / total if total > 0 else 0
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = str(datetime.utcfromtimestamp(elapsed_time / 1000).strftime('%H:%M:%S'))
        estimated_total_time = str(datetime.utcfromtimestamp(estimated_total_time / 1000).strftime('%H:%M:%S'))

        progress_str = create_progress_bar(current, total)
        
        tmp = progress_str + \
            f"\n\nProcessed: {get_readable_size(current)} / {get_readable_size(total)}\nSpeed: {get_readable_size(speed)}/s\nETA: {estimated_total_time}"
        
        try:
            await message.edit(
                text=f"{ud_type}\n\n{tmp}"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

# ---------------- BOT INIT ---------------- #
class Bot(Client):
    def __init__(self):
        super().__init__(
            name="subtitleBot",
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

        # Start queue worker
        asyncio.create_task(queue_worker(self))

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
        [InlineKeyboardButton("💻 Contact Developer", url="https://t.me/rohit_1888")]
    ])
    try:
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
    except:
        await message.reply_text(
            text=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=('@' + message.from_user.username) if message.from_user.username else None,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=keyboard
        )

# -------------- VIDEO HANDLER -------------- #
@app.on_message((filters.video | filters.audio | filters.document) & filters.private)
async def handle_video(client: Client, message: Message):
    if not message.media:
        return
    
    msg = await message.reply("⏳ Added to queue. Please wait...")
    await queue.put({"message": message, "status_msg": msg})

async def extract_audio_progress(video_path, audio_path, status_msg):
    try:
        await status_msg.edit("🎵 Extracting audio from video... This might take a bit.")
        
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path, '-y',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return audio_path
    except Exception as e:
        print(e)
        return None

def format_timestamp(seconds: float, always_include_hours: bool = False):
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000

    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000

    seconds = milliseconds // 1_000
    milliseconds -= seconds * 1_000

    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else "00:"
    return f"{hours_marker}{minutes:02d}:{seconds:02d},{milliseconds:03d}"


async def generate_subtitles(audio_path, srt_path, status_msg):
    await status_msg.edit("📝 Transcribing audio using faster-whisper... Generating Subtitles.")
    
    loop = asyncio.get_event_loop()
    
    def run_whisper():
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, beam_size=1)
        
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments, start=1):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                srt_file.write(f"{i}\n")
                srt_file.write(f"{start} --> {end}\n")
                srt_file.write(f"{segment.text.strip()}\n\n")

    await loop.run_in_executor(None, run_whisper)
    return srt_path


async def queue_worker(client: Client):
    global active_tasks
    while True:
        task = await queue.get()
        while active_tasks >= MAX_CONCURRENT_TASKS:
            await asyncio.sleep(2)
        
        active_tasks += 1
        asyncio.create_task(process_task(client, task))

async def process_task(client: Client, task):
    global active_tasks
    message = task["message"]
    status_msg = task["status_msg"]
    
    video_path = None
    audio_path = None
    srt_path = None
    
    try:
        start_time = time()
        await status_msg.edit("📥 Downloading file...")
        
        video_path = await message.download(
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading Video...", status_msg, start_time)
        )
        
        if not video_path:
            await status_msg.edit("❌ Failed to download the file.")
            active_tasks -= 1
            queue.task_done()
            return
            
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        audio_path = f"{base_name}.wav"
        srt_path = f"{base_name}.srt"
        
        extracted = await extract_audio_progress(video_path, audio_path, status_msg)
        if not extracted or not os.path.exists(audio_path):
             await status_msg.edit("❌ Failed to extract audio.")
             active_tasks -= 1
             queue.task_done()
             return
             
        await generate_subtitles(audio_path, srt_path, status_msg)
        
        if not os.path.exists(srt_path):
             await status_msg.edit("❌ Failed to generate subtitles.")
             active_tasks -= 1
             queue.task_done()
             return

        start_time = time()
        await status_msg.edit("📤 Uploading subtitle file...")
        
        sent_msg = await message.reply_document(
            document=srt_path,
            caption="Subtitle Generated Successfully!\n\nGenerated by Bot",
            progress=progress_for_pyrogram,
            progress_args=("📤 Uploading Subtitles...", status_msg, start_time)
        )
        
        try:
            await client.copy_message(
                chat_id=LOG_CHANNEL,
                from_chat_id=sent_msg.chat.id,
                message_id=sent_msg.id
            )
        except Exception:
            pass
            
        await status_msg.delete()

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        print(e)
        try:
            await status_msg.edit(f"❌ Error occurred: {str(e)[:100]}")
        except:
            pass
    finally:
        for path in [video_path, audio_path, srt_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        active_tasks -= 1
        queue.task_done()


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
import asyncio
import re
import random
import base64

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    MessageEntity
)
from aiogram.enums import ParseMode, MessageEntityType
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

# ---------------- PREMIUM EMOJI CONSTANTS ---------------- #

limit = '<tg-emoji emoji-id="5246762912428603768">📉</tg-emoji>'
rate = '<tg-emoji emoji-id="5796283422238314412">💎</tg-emoji>'
welcome = '<tg-emoji emoji-id="5206308490913531300">😊</tg-emoji>'
hello = '<tg-emoji emoji-id="5226645496067542621">🙋‍♀️</tg-emoji>'
quick = '<tg-emoji emoji-id="5440584710503825074">🈳</tg-emoji>'


# ---------------- EMOJI FUNCTIONS ---------------- #

def extract_custom_emojis(msg: Message):

    ids = []

    entities = (msg.entities or []) + (msg.caption_entities or [])

    for entity in entities:

        if entity.type == MessageEntityType.CUSTOM_EMOJI:

            if entity.custom_emoji_id:
                ids.append(str(entity.custom_emoji_id))

    return list(set(ids))


def get_html_text(msg: Message):

    text = msg.text or msg.caption or ""

    entities = msg.entities or msg.caption_entities

    if not entities:
        return text

    sorted_entities = sorted(entities, key=lambda e: e.offset, reverse=True)

    utf16_text = text.encode("utf-16-le")

    for entity in sorted_entities:

        start = entity.offset * 2
        end = (entity.offset + entity.length) * 2

        entity_text = utf16_text[start:end].decode("utf-16-le")

        replacement = None

        if entity.type == MessageEntityType.CUSTOM_EMOJI:

            eid = entity.custom_emoji_id

            replacement = f'<tg-emoji emoji-id="{eid}">{entity_text}</tg-emoji>'

        elif entity.type == MessageEntityType.BOLD:
            replacement = f"<b>{entity_text}</b>"

        elif entity.type == MessageEntityType.ITALIC:
            replacement = f"<i>{entity_text}</i>"

        elif entity.type == MessageEntityType.CODE:
            replacement = f"<code>{entity_text}</code>"

        elif entity.type == MessageEntityType.PRE:
            replacement = f"<pre>{entity_text}</pre>"

        elif entity.type == MessageEntityType.TEXT_LINK:
            replacement = f'<a href="{entity.url}">{entity_text}</a>'

        if replacement:

            utf16_text = (
                utf16_text[:start]
                + replacement.encode("utf-16-le")
                + utf16_text[end:]
            )

    return utf16_text.decode("utf-16-le")


async def apply_emoji_pack(text: str, emoji_data: list):

    if not text:
        return text

    random_pattern = re.compile(r"\{premium_?emoji\}", re.IGNORECASE)

    if not emoji_data:
        return random_pattern.sub("", text)

    import zlib

    seed = zlib.adler32(text.encode())

    gen = random.Random(seed)

    def replace_random(match):

        char, eid = gen.choice(emoji_data)

        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'

    text = random_pattern.sub(replace_random, text)

    id_to_char = {str(eid): char for char, eid in emoji_data}

    def replace_specific(match):

        eid = match.group(1)

        char = id_to_char.get(eid, "✨")

        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'

    text = re.sub(r"\{(\d{10,20})\}", replace_specific, text)

    return text


# ---------------- MESSAGE PROCESSOR ---------------- #

@dp.message()
async def handle_message(message: Message):

    if message.text and message.text.startswith("/"):

        return

    try:

        html_text = get_html_text(message)

        emoji_ids = extract_custom_emojis(message)

        emoji_data = []

        for eid in emoji_ids:
            emoji_data.append(("✨", eid))

        html_text = await apply_emoji_pack(html_text, emoji_data)

        if not html_text:

            html_text = f"""
{welcome} <b>Welcome to the bot!</b>

{hello} Hello!
{rate} Premium features available
{quick} Fast downloads supported
{limit} Usage limits may apply
"""

        post_message = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=html_text
        )

        # send back to user

        await message.answer(html_text)

        # create start link

       
    except Exception as e:

        print(e)

        await message.answer("<b>Something went wrong!</b>")


# ---------------- MAIN ---------------- #

async def main():
    await start_web_server()
    print("Bot running with Aiogram...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

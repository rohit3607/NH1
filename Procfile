worker: python3 bot.py

@app.on_callback_query(filters.regex(r"^download_(\d+)$"))
async def handle_download(client: Client, callback: CallbackQuery):
    code = callback.matches[0].group(1)
    pdf_path, msg, sent_photo, sent_pdf, thumb_path = None, None, None, None, None

    try:
        chat_id = callback.message.chat.id if callback.message else callback.from_user.id

        if callback.message:
            msg = await callback.message.reply("📥 Sᴛᴀʀᴛɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...")
        else:
            await callback.answer("📥 ᴅᴏᴡɴʟᴏᴀᴅ...")

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

        # --- Download PDF ---
        async def dl_progress(cur, total):
            await progress(cur, total, "📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ")

        pdf_path = await download_manga_as_pdf(code, dl_progress)

        # --- Get first page (for post + thumb) ---
        scraper = cloudscraper.create_scraper()
        api_url = f"https://nhentai.net/api/gallery/{code}"
        data = scraper.get(api_url).json()
        media_id = data["media_id"]
        title = data["title"]["english"] or f"Code {code}"

        first_page = data["images"]["pages"][0]   # use 1st page
        ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
        ext = ext_map.get(first_page["t"], "jpg")
        first_page_url = f"https://i.nhentai.net/galleries/{media_id}/1.{ext}"
        thumb_path = f"thumb_{code}.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(first_page_url) as resp:
                if resp.status == 200:
                    data_img = await resp.read()
                    with open(thumb_path, "wb") as f:
                        f.write(data_img)

        # --- Send first image as post ---
        sent_photo = await client.send_photo(
            chat_id,
            photo=thumb_path,
            caption=f"<b>{title}</b>\nCode: <code>{code}</code>"
        )

        if msg:
            await msg.edit("📤 Uᴘʟᴏᴀᴅɪɴɢ PDF... 0%")
        else:
            await callback.edit_message_text("📤 Uᴘʟᴏᴀᴅ... 0%")

        # --- Upload PDF with thumbnail ---
        async def upload_progress(cur, total):
            await progress(cur, total, "📤 Uᴘʟᴏᴀᴅɪɴɢ")

        sent_pdf = await client.send_document(
            chat_id,
            document=pdf_path,
            thumb=thumb_path,
            caption=f"📖 {title}\nCode: <code>{code}</code>",
            progress=upload_progress
        )

        # --- Copy both to log channel ---
        if LOG_CHANNEL != 0:
            try:
                await client.copy_message(
                    LOG_CHANNEL,
                    from_chat_id=chat_id,
                    message_id=sent_photo.id
                )
                await client.copy_message(
                    LOG_CHANNEL,
                    from_chat_id=chat_id,
                    message_id=sent_pdf.id
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.copy_message(
                    LOG_CHANNEL,
                    from_chat_id=chat_id,
                    message_id=sent_photo.id
                )
                await client.copy_message(
                    LOG_CHANNEL,
                    from_chat_id=chat_id,
                    message_id=sent_pdf.id
                )

        # --- Remove progress message ---
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
        # Cleanup
        for f in [pdf_path, thumb_path]:
            if f and os.path.exists(f):
                os.remove(f)


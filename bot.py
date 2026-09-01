import secrets
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename, MessageMediaDocument

from config import settings
from database import init_db, save_file_metadata

# Bot session uses the standard SQLite session which is fine because the bot listener is a single process.
bot = TelegramClient('bot_session', settings.api_id, settings.api_hash)

def get_file_name(document):
    if document and document.attributes:
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
    return "unknown_file"

@bot.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    if not event.media or not isinstance(event.media, MessageMediaDocument):
        # We only care about document media (files, videos, audio)
        if event.raw_text and event.raw_text.startswith('/start'):
            await event.reply("Hello! Forward any file, video, or audio to me, and I will generate a direct download link for it.")
        return

    document = event.media.document
    if not document:
        return

    # Extract required MTProto fields
    document_id = document.id
    access_hash = document.access_hash
    file_reference = document.file_reference
    file_size = document.size
    mime_type = document.mime_type
    file_name = get_file_name(document)

    # Generate cryptographically secure token
    token = secrets.token_urlsafe(16)
    
    import time
    expires_at = int(time.time()) + (settings.link_ttl_hours * 3600)

    # Store in DB
    await save_file_metadata(
        token=token,
        document_id=document_id,
        access_hash=access_hash,
        file_reference=file_reference,
        file_name=file_name,
        file_size=file_size,
        mime_type=mime_type,
        expires_at=expires_at
    )

    download_link = f"{settings.base_url.rstrip('/')}/d/{token}"
    
    await event.reply(
        f"**File Link Generated:**\n\n"
        f"**Name:** `{file_name}`\n"
        f"**Size:** `{file_size} bytes`\n"
        f"**Link:**\n{download_link}",
        link_preview=False
    )

async def main():
    await init_db()
    await bot.start(bot_token=settings.bot_token)
    print("Bot is running...")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())

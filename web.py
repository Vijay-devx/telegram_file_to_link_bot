import math
import urllib.parse
import time
from fastapi import FastAPI, Request, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, Response, PlainTextResponse
from contextlib import asynccontextmanager

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.tl.types import InputDocumentFileLocation
from telethon import errors

from config import settings
from database import get_file_metadata, init_db, delete_expired_links

# Use MemorySession so multiple web workers don't lock the sqlite database used by bot.py
web_client = TelegramClient(MemorySession(), settings.api_id, settings.api_hash)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await web_client.start(bot_token=settings.bot_token)
    yield
    await web_client.disconnect()

app = FastAPI(lifespan=lifespan)

def parse_range_header(range_header: str, file_size: int):
    """
    Parses the Range header and returns a tuple of (start, end).
    If invalid, returns None.
    If no range header, returns (0, file_size - 1).
    """
    if not range_header:
        return 0, file_size - 1
    
    try:
        if not range_header.startswith("bytes="):
            return None
        range_str = range_header.split("=")[1].strip()
        
        # Handle simple bytes=0-100 or bytes=100- cases
        if "," in range_str:
            # We don't support multiple ranges for simplicity, standard tools are fine with this
            return None
            
        start_str, end_str = range_str.split("-")
        
        if start_str == "":
            # bytes=-500 (last 500 bytes)
            suffix_length = int(end_str)
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        else:
            start = int(start_str)
            if end_str == "":
                end = file_size - 1
            else:
                end = int(end_str)
                
        if start >= file_size or end >= file_size or start > end:
            return None
            
        return start, end
    except Exception:
        return None

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamer")

async def stream_file(location: InputDocumentFileLocation, start: int, end: int):
    bytes_to_read = end - start + 1
    bytes_read = 0
    
    logger.info(f"Starting stream for document {location.id}, start={start}, end={end}")
    try:
        async for chunk in web_client.iter_download(location, offset=start):
            remaining = bytes_to_read - bytes_read
            if len(chunk) > remaining:
                yield chunk[:remaining]
                bytes_read += remaining
                break
            else:
                yield chunk
                bytes_read += len(chunk)
                if bytes_read == bytes_to_read:
                    break
    except (errors.FileReferenceExpiredError, errors.FileReferenceInvalidError) as e:
        logger.warning("Telegram file reference expired during streaming.")
        # We break cleanly so the socket closes without dropping a crash message,
        # allowing download managers to know the stream ended gracefully (though incomplete).
    except errors.FloodWaitError as e:
        logger.warning(f"Flood wait error during streaming, waiting {e.seconds} seconds.")
    except Exception as e:
        error_msg = f"\n\n--- SERVER CRASH REASON ---\n{type(e).__name__}: {str(e)}\n---------------------------\n"
        logger.error(error_msg)
        yield error_msg.encode('utf-8')
    finally:
        logger.info(f"Stream finished. Read {bytes_read}/{bytes_to_read} bytes.")

@app.head("/d/{token}")
@app.get("/d/{token}")
async def download_file(token: str, request: Request, background_tasks: BackgroundTasks):
    metadata = await get_file_metadata(token)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
        
    if time.time() > metadata["expires_at"]:
        return PlainTextResponse(
            "This download link has expired. Please forward the file to the bot again to generate a new link.",
            status_code=status.HTTP_410_GONE
        )
        
    # Trigger database cleanup lightly in the background
    background_tasks.add_task(delete_expired_links, settings.db_path)
        
    file_size = metadata["file_size"]
    file_name = metadata["file_name"]
    mime_type = metadata["mime_type"] or "application/octet-stream"
    
    # Generate InputDocumentFileLocation for MTProto download
    location = InputDocumentFileLocation(
        id=metadata["document_id"],
        access_hash=metadata["access_hash"],
        file_reference=metadata["file_reference"],
        thumb_size=''
    )
    
    range_header = request.headers.get("Range")
    
    if range_header:
        range_info = parse_range_header(range_header, file_size)
        if not range_info:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"}
            )
            
        start, end = range_info
        status_code = status.HTTP_206_PARTIAL_CONTENT
    else:
        start = 0
        end = file_size - 1
        status_code = status.HTTP_200_OK
        
    content_length = end - start + 1
    
    # Safely encode filename for Content-Disposition
    encoded_filename = urllib.parse.quote(file_name)
    content_disposition = f"attachment; filename=\"{file_name}\"; filename*=UTF-8''{encoded_filename}"
    
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
        "Content-Disposition": content_disposition,
        "X-Accel-Buffering": "no"  # Critical for NGINX proxy environments like PythonAnywhere
    }
    
    if status_code == status.HTTP_206_PARTIAL_CONTENT:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        
    if request.method == "HEAD":
        return Response(status_code=status_code, headers=headers)
        
    return StreamingResponse(
        stream_file(location, start, end),
        status_code=status_code,
        headers=headers,
        media_type=mime_type
    )

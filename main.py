import os
import re
import json
import asyncio
from typing import Dict
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from fastapi import FastAPI
import uvicorn
import sys

#loop
try:
    asyncio.get_event_loop_policy().get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ================= CONFIGURATION =================
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

OWNER_ID = 5421311764
SLAVE_CHAT_ID = int(os.getenv("SLAVE_CHAT_ID", "-1001234567890"))
PORT = int(os.getenv("PORT", 8080))

# In-memory session taaki Render par file lock ka error na aaye
bot = Client("Lakshitsir_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
PENDING_REQUESTS: Dict[int, asyncio.Future] = {}
app = FastAPI()

# ================= DATABASE / GROUPS =================
GROUPS_FILE = "approved_groups.json"

def load_groups() -> set:
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_groups(groups: set):
    with open(GROUPS_FILE, "w") as f:
        json.dump(list(groups), f)

APPROVED_GROUPS = load_groups()

# ================= FASTAPI HEALTH =================
@app.get("/")
def health_check():
    return {"status": "Lakshitsir Premium Engine Alive", "developer": "Lakshit Patidar"}

# ================= EXTREME CREDIT CLEANER =================
def sanitize_credits(text: str) -> str:
    if not text: return ""
    
    # 1. Remove all links
    text = re.sub(r'https?://\S+', '', text)
    
    # 2. Remove all telegram tags except yours
    tags = re.findall(r'@[a-zA-Z0-9_]+', text)
    for tag in tags:
        if tag.lower() != "@lakshitpatidar":
            text = text.replace(tag, "")
            
    # Remove any existing @lakshitpatidar so we can cleanly add it at the bottom later
    text = re.sub(r'@lakshitpatidar', '', text, flags=re.IGNORECASE)
    
    # 3. Strip out common bot watermarks completely
    lines = []
    for line in text.split('\n'):
        lower_line = line.lower()
        if any(x in lower_line for x in ["owner:", "developer:", "dev:", "powered by:", "bot by:", "credit:", "channel:"]):
            continue
        lines.append(line)
        
    text = "\n".join(lines)
    
    # 4. Mandatory Aadhaar Redaction (Privacy Protocol)
    text = re.sub(r'\b\d{12}\b', '[Aadhaar Redacted]', text)
    
    return text.strip()

# ================= SMART PROCESSING FILTER =================
def is_processing_msg(text: str) -> bool:
    """
    Ab ye length nahi dekhta, context dekhta hai! 
    Agar chota data aaya to ye usko block NAHI karega.
    """
    text_lower = text.lower().strip()
    words = text_lower.split()
    
    # Agar message me sirf 1 se 5 words hain aur ye keywords hain -> ignore
    processing_keywords = ["processing", "wait", "searching", "fetching", "finding", "loading"]
    if len(words) <= 5 and any(k in text_lower for k in processing_keywords):
        return True
        
    # Agar usme loading emoji hai aur message chota hai -> ignore
    if any(emoji in text for emoji in ["⏳", "🔄", "🔍", "⏱"]) and len(text) < 50:
        return True
        
    return False # Agar real data hai, to pass hone do!

# ================= FORMATTERS =================
def format_final_response(raw_text: str, cmd_type: str) -> list:
    clean_text = sanitize_credits(raw_text)
    
    if not clean_text:
        return ["❌ **NO DATA FOUND**\n━━━━━━━━━━━━━━━━━━━━\n_Database returned an empty response._\n\n⚡ **Powered by:** `@lakshitpatidar`"]

    # For pure text/TG responses
    if cmd_type == "tg" or not clean_text.startswith("{") and not clean_text.startswith("["):
        body = clean_text.strip()
        out = f"💠 **LOOKUP RESULT**\n━━━━━━━━━━━━━━━━━━━━\n\n{body}\n\n━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered by:** `@lakshitpatidar`"
        return [out]

    # For JSON format responses
    try:
        data = json.loads(clean_text)
        results = data.get("results", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        
        if not results:
            return ["❌ **NO DATA FOUND**\n━━━━━━━━━━━━━━━━━━━━\n_No records found._\n\n⚡ **Powered by:** `@lakshitpatidar`"]

        messages = []
        header = f"🔎 **ADVANCED LOOKUP** | **{len(results)} Records**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        batch_size = 3
        for i in range(0, len(results), batch_size):
            batch = results[i:i + batch_size]
            out = header if i == 0 else f"📑 **PAGE {i//batch_size + 1}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for idx, item in enumerate(batch, i + 1):
                out += f"👤 **RECORD #{idx}**\n"
                for key, val in item.items():
                    if val and str(val).strip() != "":
                        key_title = str(key).replace("_", " ").title()
                        out += f" ├ **{key_title}:** `{val}`\n"
                out += "\n"
                
            out += "━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered by:** `@lakshitpatidar`"
            messages.append(out)

        return messages
    except Exception:
        # Fallback if it looks like json but fails parsing
        out = f"💠 **LOOKUP RESULT**\n━━━━━━━━━━━━━━━━━━━━\n\n{clean_text}\n\n━━━━━━━━━━━━━━━━━━━━\n⚡ **Powered by:** `@lakshitpatidar`"
        return [out]

# ================= COMMAND HANDLERS =================
@bot.on_message(filters.command(["start", "help"]) & (filters.private | filters.group))
async def help_cmd(client: Client, message: Message):
    help_text = (
        "🛡 **LAKSHITSIR SECURE ENGINE** 🛡\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "**🔍 Modules:** `/num`, `/adhar`, `/tg`\n"
        "**⚙️ Admin:** `/approvegc`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 **Developer:** `@lakshitpatidar`"
    )
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

@bot.on_message(filters.command("approvegc") & filters.group)
async def approve_gc(client: Client, message: Message):
    if message.from_user and message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ **Denied:** _Only Lakshitsir can do this._")
    
    chat_id = message.chat.id
    if chat_id not in APPROVED_GROUPS:
        APPROVED_GROUPS.add(chat_id)
        save_groups(APPROVED_GROUPS)
    await message.reply_text("✅ **Group Authorized!**")

@bot.on_message(filters.command(["tg", "num", "adhar"]) & (filters.private | filters.group))
async def handle_lookups(client: Client, message: Message):
    chat_id = message.chat.id
    if message.chat.type.name == "PRIVATE" and message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ **Access Restricted:** _Owner Only._")
    if message.chat.type.name in ["GROUP", "SUPERGROUP"] and chat_id not in APPROVED_GROUPS:
        return await message.reply_text("❌ **Unauthorized Space.**")

    if len(message.command) < 2:
        return await message.reply_text(f"⚠️ **Syntax:** `/{message.command[0]} <query>`")

    cmd = message.command[0]
    status_msg = await message.reply_text("🔄 _Extracting data..._")

    try:
        sent_in_seed = await client.send_message(chat_id=SLAVE_CHAT_ID, text=message.text)
        loop = asyncio.get_running_loop()
        reply_future = loop.create_future()
        PENDING_REQUESTS[sent_in_seed.id] = reply_future

        try:
            # 30 seconds max wait time for the slave bot to give real data
            final_text = await asyncio.wait_for(reply_future, timeout=30.0)
            messages = format_final_response(final_text, cmd)

            await status_msg.edit_text(messages[0], disable_web_page_preview=True)
            
            # Send paginated data to avoid Telegram's message length limits
            if len(messages) > 1:
                for ext_msg in messages[1:]:
                    await asyncio.sleep(1.5) 
                    await client.send_message(chat_id, ext_msg, disable_web_page_preview=True)

        except asyncio.TimeoutError:
            await status_msg.edit_text("❌ **TIMEOUT ERROR**\n_Target database didn't respond in time._\n\n⚡ **Source:** `@lakshitpatidar`")

        PENDING_REQUESTS.pop(sent_in_seed.id, None)

    except Exception as e:
        await status_msg.edit_text(f"❌ **SYSTEM ERROR**\n`{str(e)}`\n\n⚡ **Source:** `@lakshitpatidar`")

# ================= SLAVE CAPTURE LOGIC =================
@bot.on_message(filters.chat(SLAVE_CHAT_ID) & ~filters.me)
@bot.on_edited_message(filters.chat(SLAVE_CHAT_ID) & ~filters.me)
async def capture_slave_replies(client: Client, message: Message):
    text = message.text or message.caption or ""
    if not text:
        return

    # Reject fake processing edits
    if is_processing_msg(text):
        return

    # Check if the slave bot is replying to our original command
    if message.reply_to_message and message.reply_to_message.id in PENDING_REQUESTS:
        future = PENDING_REQUESTS[message.reply_to_message.id]
        if not future.done():
            future.set_result(text)
            
    # Fallback: Agar slave bot bina reply kiye direct message bhej raha hai
    # Toh hum latest pending request ko fulfill kar denge
    elif PENDING_REQUESTS:
        latest_req_id = max(PENDING_REQUESTS.keys())
        future = PENDING_REQUESTS[latest_req_id]
        if not future.done():
            future.set_result(text)

# ================= SERVER ENTRY =================
async def main():
    await bot.start()
    print("🚀 Lakshitsir Premium Bot Started!")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
            

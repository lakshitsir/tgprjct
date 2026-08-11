import os
import re
import json
import asyncio
from typing import Dict
from fastapi import FastAPI, Request
from pyrogram import Client, filters
from pyrogram.types import Message

# ================= CONFIGURATION =================
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

OWNER_ID = 5421311764
SLAVE_CHAT_ID = int(os.getenv("SLAVE_CHAT_ID", "-1001234567890"))

# Approved Groups Whitelist
APPROVED_GROUPS = {-1009876543210, -1001122334455}

app = FastAPI()

# in_memory=True stops Pyrogram from writing to Vercel's read-only disk
bot = Client(
    "VercelBot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    in_memory=True
)

PENDING_REQUESTS: Dict[int, dict] = {}


# ================= CLEANERS =================
def sanitize_credits(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r't\.me/\S+', '', text)

    tags = re.findall(r'@[a-zA-Z0-9_]+', text)
    for tag in tags:
        if tag.lower() != "@lakshitpatidar":
            text = text.replace(tag, "")

    text = re.sub(r'@lakshitpatidar', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d{12}\b', '[Aadhaar Redacted]', text)

    return text.strip()


def format_tg_response(raw_text: str) -> str:
    clean_text = sanitize_credits(raw_text)
    clean_lines = []
    for line in clean_text.splitlines():
        if any(keyword in line.lower() for keyword in ["owner:", "developer:", "dev:", "powered by:"]):
            continue
        clean_lines.append(line)

    body = "\n".join(clean_lines).strip()
    return f"{body}\n\n━━━━━━━━━━━━━━\n⚡ **Source:** `@lakshitpatidar`"


def format_json_response(raw_text: str) -> str:
    clean_raw = sanitize_credits(raw_text)

    try:
        data = json.loads(clean_raw)
        results = data.get("results", [])

        if not results:
            return "❌ **SEARCH RESULT**\n\n_No records found in database._\n\n⚡ **Source:** `@lakshitpatidar`"

        total_count = data.get("count", len(results))

        linked_numbers = []
        for item in results:
            m = str(item.get("mobile", "")).strip()
            if m and m not in linked_numbers:
                linked_numbers.append(m)
            alt = str(item.get("alt", "")).strip()
            if alt and alt.lower() != "n/a" and alt not in linked_numbers:
                linked_numbers.append(alt)

        out = f"🔎 **LOOKUP RESULTS** — __Found {total_count} Record(s)__\n\n"

        if linked_numbers:
            out += "📱 **Attached Mobile Numbers:**\n"
            for num in linked_numbers:
                out += f"   • `{num}`\n"
            out += f"   📊 **Total Unique:** `{len(linked_numbers)}`\n\n━━━━━━━━━━━━━━\n\n"

        known_keys = {"id", "name", "fname", "mobile", "circle", "address", "email", "alt"}

        for idx, item in enumerate(results, 1):
            name = str(item.get("name", "N/A")).strip().title()
            fname = str(item.get("fname", "N/A")).strip().title()
            mobile = str(item.get("mobile", "N/A")).strip()
            circle = str(item.get("circle", "N/A")).strip().upper()
            address = str(item.get("address", "N/A")).strip().title()
            email = str(item.get("email") or "N/A").strip()
            alt = str(item.get("alt") or "N/A").strip()

            out += f"📄 **Result #{idx}**\n"
            out += f"• **Name:** __`{name}`__\n"
            out += f"• **Father:** _{fname}_\n"
            out += f"• **Mobile:** `{mobile}`\n"
            out += f"• **Circle/SIM:** _{circle}_\n"
            out += f"• **Address:** _{address}_\n"
            out += f"• **Aadhaar ID:** `[Aadhaar Redacted]`\n"
            out += f"• **Email:** _{email}_\n"
            out += f"• **Alt Number:** `{alt}`\n"

            for key, val in item.items():
                if key not in known_keys and val:
                    key_title = key.replace("_", " ").title()
                    out += f"• **{key_title}:** _{val}_\n"

            out += "\n"

        out += "━━━━━━━━━━━━━━\n⚡ **Source:** `@lakshitpatidar`"
        return out

    except Exception:
        lines = [line.strip() for line in clean_raw.splitlines() if line.strip()]
        formatted_lines = [f"• _{line}_" if ":" not in line else f"• **{line.split(':', 1)[0].strip().title()}:** _{line.split(':', 1)[1].strip()}_" for line in lines]

        out = "🔎 **SEARCH RESULTS**\n\n"
        out += "\n".join(formatted_lines) + "\n\n"
        out += "━━━━━━━━━━━━━━\n⚡ **Source:** `@lakshitpatidar`"
        return out


# ================= COMMAND HANDLERS =================
COMMANDS = ["tg", "num", "adhar"]

@bot.on_message(filters.command(COMMANDS) & (filters.private | filters.group))
async def handle_commands(client: Client, message: Message):
    chat_id = message.chat.id
    chat_type = message.chat.type.name

    if chat_type == "PRIVATE" and message.from_user.id != OWNER_ID:
        await message.reply_text("❌ **Access Restricted:** _Commands are owner-only in DM._")
        return
    elif chat_type in ["GROUP", "SUPERGROUP"] and chat_id not in APPROVED_GROUPS:
        await message.reply_text("❌ **Unauthorized Group:** _This group is not whitelisted._")
        return

    if len(message.command) < 2:
        cmd = message.command[0]
        await message.reply_text(f"⚠️ **Usage:** `/{cmd} <query_value>`")
        return

    cmd = message.command[0]
    query_val = " ".join(message.command[1:])
    full_cmd_text = f"/{cmd} {query_val}"

    status_msg = await message.reply_text("🔍 _Searching database, please wait..._")

    try:
        target_msg_id = None
        async for old_msg in client.get_chat_history(SLAVE_CHAT_ID, limit=30):
            if old_msg.from_user and old_msg.from_user.username and old_msg.from_user.username.lower() == "snxinfoxbot":
                target_msg_id = old_msg.id
                break

        if not target_msg_id:
            async for old_msg in client.get_chat_history(SLAVE_CHAT_ID, limit=1):
                target_msg_id = old_msg.id

        if not target_msg_id:
            await status_msg.edit_text("❌ **Error:** _Unable to establish connection with seed group history._")
            return

        sent_in_seed = await client.send_message(
            chat_id=SLAVE_CHAT_ID,
            text=full_cmd_text,
            reply_to_message_id=target_msg_id
        )

        PENDING_REQUESTS[sent_in_seed.id] = {
            "chat_id": chat_id,
            "status_msg_id": status_msg.id,
            "cmd": cmd,
            "responses": []
        }

        # Keep sleep time within Vercel's execution window
        wait_time = 5 if cmd in ["num", "adhar"] else 4
        await asyncio.sleep(wait_time)

        req_data = PENDING_REQUESTS.pop(sent_in_seed.id, None)
        if not req_data or not req_data["responses"]:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.id,
                text="❌ **SEARCH RESULT**\n\n_No response received from slave bot or request timed out._\n\n⚡ **Source:** `@lakshitpatidar`"
            )
            return

        best_response = max(req_data["responses"], key=len)

        if cmd == "tg":
            final_output = format_tg_response(best_response)
        else:
            final_output = format_json_response(best_response)

        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=final_output,
            disable_web_page_preview=True
        )

    except Exception as e:
        await client.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.id,
            text=f"❌ **SYSTEM ERROR**\n\n`{str(e)}`\n\n⚡ **Source:** `@lakshitpatidar`"
        )


@bot.on_message(filters.chat(SLAVE_CHAT_ID) & ~filters.me)
async def capture_slave_replies(client: Client, message: Message):
    raw_text = message.text or message.caption or ""
    if not raw_text:
        return

    if message.reply_to_message and message.reply_to_message.id in PENDING_REQUESTS:
        PENDING_REQUESTS[message.reply_to_message.id]["responses"].append(raw_text)
        return

    if PENDING_REQUESTS:
        latest_key = list(PENDING_REQUESTS.keys())[-1]
        PENDING_REQUESTS[latest_key]["responses"].append(raw_text)


# ================= WEBHOOK LIFECYCLE =================
@app.post("/")
async def telegram_webhook(request: Request):
    try:
        if not bot.is_connected:
            await bot.start()

        data = await request.json()
        update = Message.de_json(bot, data)
        if update:
            await bot.process_new_messages([update])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
            

import json
import os
import io
import time
from functools import wraps
from telegram import (
    Update, InputMediaPhoto, InputMediaVideo, InputMediaAnimation
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ===== Load environment variables =====
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")
ADMINS = [int(x.strip()) for x in ADMIN_IDS.split(",") if x.strip().isdigit()]
REPLIES_FILE = "replies.json"
COOLDOWN_SECONDS = 10

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found. Please set it as an environment variable.")

# ===== Globals =====
replies = {}
temp_storage = {}
welcome_message = "👋 Welcome!"
last_used = {}

# ===== Helpers =====
def save_replies():
    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(replies, f, indent=2)

def load_replies():
    global replies
    if os.path.exists(REPLIES_FILE):
        with open(REPLIES_FILE, "r", encoding="utf-8") as f:
            replies = json.load(f)

async def is_group_admin(update: Update):
    chat = update.effective_chat
    user = update.effective_user
    if chat.type in ["group", "supergroup"]:
        member = await chat.get_member(user.id)
        return member.status in ["administrator", "creator"]
    return False

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMINS and not await is_group_admin(update):
            await update.message.reply_text("🚫 You don’t have permission to use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ===== Commands =====
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is active and running!")

@admin_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🛠 **Bot Commands**
• /start — Check bot status  
• /help — Show this help  
• /setwelcome <msg> — Set welcome message  
• /setreply <keyword> — Add a new reply (media/text/file)  
• /done — Finish adding reply  
• /listreplies — List all saved replies  
• /addalias <keyword> <aliases> — Add alias words  
• /deletereply <keyword> — Delete a reply  
• /exportreplies — Export replies as JSON  
• /importreplies — Import replies from uploaded JSON  
(Use @BotMention <keyword> to trigger in groups)
"""
    await update.message.reply_text(text, parse_mode="Markdown")

@admin_only
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global welcome_message
    if not context.args:
        await update.message.reply_text("Usage: /setwelcome <message>")
        return
    welcome_message = " ".join(context.args)
    await update.message.reply_text(f"✅ Welcome message set to:\n{welcome_message}")

@admin_only
async def set_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setreply <keyword>")
        return
    key = " ".join(context.args).lower().strip()
    temp_storage[update.effective_user.id] = {"key": key, "items": []}
    await update.message.reply_text(
        f"📥 Send media/files/text for *{key}*. When done, send /done.",
        parse_mode="Markdown"
    )

@admin_only
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in temp_storage or not temp_storage[user_id]["items"]:
        await update.message.reply_text("⚠️ No media or text received, nothing saved.")
        return
    data = temp_storage.pop(user_id)
    key = data["key"]
    replies[key] = {"items": data["items"], "aliases": []}
    save_replies()
    await update.message.reply_text(f"✅ Saved reply for keyword: *{key}*", parse_mode="Markdown")

@admin_only
async def list_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not replies:
        await update.message.reply_text("📂 No replies saved yet.")
        return
    msg = "\n".join([f"• {k} (aliases: {', '.join(v.get('aliases', [])) or 'None'})" for k, v in replies.items()])
    await update.message.reply_text(f"🗂 Saved Replies:\n{msg}")

@admin_only
async def add_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addalias <keyword> <aliases>")
        return
    key = context.args[0].lower().strip()
    aliases = [x.lower() for x in context.args[1:]]
    if key not in replies:
        await update.message.reply_text("⚠️ Keyword not found.")
        return
    replies[key].setdefault("aliases", []).extend(aliases)
    save_replies()
    await update.message.reply_text(f"✅ Added aliases for *{key}*: {', '.join(aliases)}", parse_mode="Markdown")

@admin_only
async def delete_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deletereply <keyword>")
        return
    key = " ".join(context.args).lower().strip()
    if key in replies:
        replies.pop(key)
        save_replies()
        await update.message.reply_text(f"🗑 Deleted reply for *{key}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ No such keyword found.")

@admin_only
async def export_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not replies:
        await update.message.reply_text("No replies to export.")
        return
    buf = io.BytesIO(json.dumps(replies, indent=2).encode())
    buf.name = "replies_export.json"
    await update.message.reply_document(buf)

@admin_only
async def import_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Please attach a JSON file to import.")
        return
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    data = json.loads(content.decode())
    replies.update(data)
    save_replies()
    await update.message.reply_text(f"✅ Imported {len(data)} replies successfully.")

# ===== Message listener =====
async def message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    chat_type = update.effective_chat.type
    text = (message.text or message.caption or "").lower().strip()
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot_username = context.bot.username.lower()

    print(f"[DEBUG] chat={chat_type}, user={user_id}, text={text}")

    # Handle adding replies
    if user_id in temp_storage:
        data = temp_storage[user_id]
        item = None
        if message.photo:
            item = {"type": "photo", "file_id": message.photo[-1].file_id}
        elif message.video:
            item = {"type": "video", "file_id": message.video.file_id}
        elif message.animation:
            item = {"type": "animation", "file_id": message.animation.file_id}
        elif message.audio:
            item = {"type": "audio", "file_id": message.audio.file_id}
        elif message.document:
            item = {"type": "document", "file_id": message.document.file_id}
        elif message.text:
            item = {"type": "text", "content": message.text}

        if item:
            data["items"].append(item)
        return

    # In groups: only respond when mentioned
    if chat_type in ["group", "supergroup"]:
        if f"@{bot_username}" not in text:
            return
        text = text.replace(f"@{bot_username}", "").strip()

    # Handle replies
    for key, val in replies.items():
        if text == key or text in val.get("aliases", []):
            now = time.time()
            cooldown_key = (chat_id, key)
            if now - last_used.get(cooldown_key, 0) < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - (now - last_used[cooldown_key]))
                await message.reply_text(f"⏳ Please wait {remaining}s before sending next message.")
                return
            last_used[cooldown_key] = now

            items = val.get("items", [])
            media_group = []
            for item in items:
                t = item["type"]
                if t == "photo":
                    media_group.append(InputMediaPhoto(item["file_id"]))
                elif t == "video":
                    media_group.append(InputMediaVideo(item["file_id"]))
                elif t == "animation":
                    media_group.append(InputMediaAnimation(item["file_id"]))
            if media_group:
                await message.reply_media_group(media_group)
            for item in items:
                t = item["type"]
                if t == "text":
                    await message.reply_text(item["content"])
                elif t == "document":
                    await message.reply_document(item["file_id"])
                elif t == "audio":
                    await message.reply_audio(item["file_id"])

# ===== Main =====
if __name__ == "__main__":
    load_replies()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("setwelcome", set_welcome))
    app.add_handler(CommandHandler("setreply", set_reply))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("listreplies", list_replies))
    app.add_handler(CommandHandler("addalias", add_alias))
    app.add_handler(CommandHandler("deletereply", delete_reply))
    app.add_handler(CommandHandler("exportreplies", export_replies))
    app.add_handler(CommandHandler("importreplies", import_replies))

    app.add_handler(MessageHandler(filters.ALL, message_listener))

    print("🤖 Bot is running...")
    app.run_polling()

import json
import os
import io
import time
from functools import wraps
from telegram import (
    Update, InputMediaPhoto, InputMediaVideo,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN", "7696190550:AAG32P5wcNR8BKEPYUh0He_dVqe0vE-QTQ0")
REPLIES_FILE = "replies.json"
ADMINS = [1609779071]  # Replace with your Telegram numeric user ID(s)
COOLDOWN_SECONDS = 10  # cooldown per keyword per chat
# ==========================

# ========= GLOBAL DATA =========
replies = {}
temp_storage = {}  # Temporary storage for admins adding replies
welcome_message = "👋 Welcome to the group!"
last_used = {}  # {(chat_id, keyword): timestamp}
os.makedirs("data", exist_ok=True)

# ========= UTILS =========
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

# ========= COMMANDS =========
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is active and ready!")

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
async def add_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addalias <keyword> <alias1, alias2,...>")
        return
    key = context.args[0].lower().strip()
    if key not in replies:
        await update.message.reply_text(f"❌ No reply found for '{key}'")
        return
    aliases = [a.strip().lower() for a in " ".join(context.args[1:]).split(",")]
    replies[key].setdefault("aliases", []).extend(aliases)
    save_replies()
    await update.message.reply_text(f"✅ Added aliases for *{key}*: {', '.join(aliases)}", parse_mode="Markdown")

@admin_only
async def delete_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /deletereply <keyword>")
        return
    key = " ".join(context.args).lower().strip()
    if key not in replies:
        await update.message.reply_text(f"❌ No reply found for '{key}'")
        return
    del replies[key]
    save_replies()
    await update.message.reply_text(f"🗑️ Deleted reply for: *{key}*", parse_mode="Markdown")

@admin_only
async def list_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not replies:
        await update.message.reply_text("📭 No replies saved yet.")
        return
    for key, val in replies.items():
        counts = {"photo":0,"video":0,"document":0,"text":0}
        for item in val.get("items", []):
            t = item["type"]
            counts[t] = counts.get(t,0)+1
        summary = ", ".join(f"{n} {t}{'s' if n>1 else ''}" for t,n in counts.items() if n>0)
        alias_list = ", ".join(val.get("aliases", [])) or "—"
        msg_text = f"🔑 *{key}*\n📦 {summary}\n🪶 Aliases: {alias_list}"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👀 Preview", callback_data=f"preview|{key}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete|{key}")
            ]
        ])
        await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=keyboard)

@admin_only
async def export_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not replies:
        await update.message.reply_text("📭 No replies to export.")
        return
    data = json.dumps(replies, indent=2)
    bio = io.BytesIO(data.encode("utf-8"))
    bio.name = "replies_backup.json"
    await update.message.reply_document(bio, caption="📤 Exported all replies.")

@admin_only
async def import_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("⚠️ Please attach a JSON file.")
        return
    file = await update.message.document.get_file()
    content = await file.download_as_bytearray()
    data = json.loads(content.decode("utf-8"))
    imported = 0
    for k,v in data.items():
        replies[k] = v
        imported += 1
    save_replies()
    await update.message.reply_text(f"📥 Imported {imported} reply sets successfully!")

# ========= CALLBACK HANDLER =========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, key = query.data.split("|")
    if action == "delete":
        if key in replies:
            del replies[key]
            save_replies()
            await query.message.reply_text(f"🗑️ Deleted reply for '{key}'")
    elif action == "preview":
        entry = replies.get(key, {})
        items = entry.get("items", [])
        if not items:
            await query.message.reply_text("⚠️ No content for this keyword.")
            return
        media_group = []
        for item in items:
            if item["type"]=="photo":
                media_group.append(InputMediaPhoto(item["file_id"]))
            elif item["type"]=="video":
                media_group.append(InputMediaVideo(item["file_id"]))
        if media_group:
            await query.message.reply_media_group(media_group)
        for item in items:
            if item["type"]=="text":
                await query.message.reply_text(item["content"])
            elif item["type"]=="document":
                await query.message.reply_document(item["file_id"])

# ========= MESSAGE LISTENER =========
async def message_listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = (message.text or "").lower().strip()

    # ----------- Check temp storage (admin adding replies) -----------
    if user_id in temp_storage:
        data = temp_storage[user_id]
        item = None
        # Capture media/files/text regardless of mention
        if message.photo:
            item = {"type": "photo", "file_id": message.photo[-1].file_id}
        elif message.video:
            item = {"type": "video", "file_id": message.video.file_id}
        elif message.document:
            item = {"type": "document", "file_id": message.document.file_id}
        elif message.text and not message.text.startswith("/"):
            item = {"type": "text", "content": message.text}
        if item:
            data["items"].append(item)
        return  # Do not process further

    # ----------- Mention-only trigger for normal replies -----------
    bot_username = context.bot.username.lower()
    if chat_id > 0:
        # Private chat: respond normally without mention
        text_to_check = text
    else:
        # Group chat: only respond if bot is mentioned
        if f"@{bot_username}" not in text:
            return
        text_to_check = text.replace(f"@{bot_username}", "").strip()

    # ----------- Keyword auto-reply with cooldown -----------
    for key, val in replies.items():
        if text_to_check == key or text_to_check in val.get("aliases", []):
            now = time.time()
            cooldown_key = (chat_id, key)
            last_time = last_used.get(cooldown_key, 0)
            if now - last_time < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - (now - last_time))
                await message.reply_text(f"⏳ Please wait {remaining}s before sending next message.")
                return
            last_used[cooldown_key] = now

            items = val.get("items", [])
            media_group = []
            for item in items:
                if item["type"] == "photo":
                    media_group.append(InputMediaPhoto(item["file_id"]))
                elif item["type"] == "video":
                    media_group.append(InputMediaVideo(item["file_id"]))
            if media_group:
                await message.reply_media_group(media_group)
            for item in items:
                if item["type"] == "text":
                    await message.reply_text(item["content"])
                elif item["type"] == "document":
                    await message.reply_document(item["file_id"])

# ========= WELCOME =========
async def welcome_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"{welcome_message} {member.first_name}!")

# ========= MAIN =========
if __name__ == "__main__":
    load_replies()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwelcome", set_welcome))
    app.add_handler(CommandHandler("setreply", set_reply))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("addalias", add_alias))
    app.add_handler(CommandHandler("deletereply", delete_reply))
    app.add_handler(CommandHandler("listreplies", list_replies))
    app.add_handler(CommandHandler("exportreplies", export_replies))
    app.add_handler(CommandHandler("importreplies", import_replies))

    # Callback handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Welcome new members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_user))

    # Message listener for keywords
    app.add_handler(MessageHandler(filters.ALL, message_listener))

    print("🤖 Bot is running...")
    app.run_polling()

import os
import json
import asyncio
from dotenv import load_dotenv
from telegram import (
    Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from datetime import datetime, timedelta

# === Load environment variables ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS", "")
ADMINS = [int(x.strip()) for x in ADMIN_IDS.split(",") if x.strip().isdigit()]

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found. Please set it as an environment variable.")

# === File paths ===
REPLIES_FILE = "replies.json"
COOLDOWN_SECONDS = 10
last_user_message_time = {}

# === Data storage ===
if os.path.exists(REPLIES_FILE):
    with open(REPLIES_FILE, "r") as f:
        replies = json.load(f)
else:
    replies = {}

# === Helper functions ===
def save_replies():
    with open(REPLIES_FILE, "w") as f:
        json.dump(replies, f, indent=2)

async def is_admin(user, chat):
    if user.id in ADMINS:
        return True
    if chat.type in ["group", "supergroup"]:
        member = await chat.get_member(user.id)
        return member.status in ["administrator", "creator"]
    return False

# === Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! I'm your group assistant bot.\nUse /help to see what I can do.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Available Commands:*\n\n"
        "/start – Greet the bot\n"
        "/help – Show this help message\n"
        "/setreply <keyword> – Set up media/text replies for a keyword (Admin only)\n"
        "/done – Save the reply setup (after sending media/files)\n"
        "/deletereply <keyword> – Delete a keyword’s reply (Admin only)\n"
        "/listreplies – List all configured keywords\n\n"
        "💡 *Usage Tips:*\n"
        "- Mention the bot (@your_bot_name) with a keyword to trigger replies.\n"
        "- Media, GIFs, audio, and files are supported.\n"
        "- Cooldown: 10 seconds per user to prevent spam."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# === Admin: Set replies ===
user_sessions = {}

async def setreply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not await is_admin(user, chat):
        return await update.message.reply_text("🚫 Only admins can set replies.")
    if len(context.args) == 0:
        return await update.message.reply_text("Usage: `/setreply <keyword>`", parse_mode="Markdown")

    keyword = " ".join(context.args).lower()
    user_sessions[user.id] = {"keyword": keyword, "media": []}
    await update.message.reply_text(
        f"✅ Send the media, files, or messages for *'{keyword}'*.\nWhen done, type `/done`.",
        parse_mode="Markdown"
    )

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in user_sessions:
        return await update.message.reply_text("⚠️ No reply setup in progress.")
    data = user_sessions[user.id]
    keyword = data["keyword"]
    media = data["media"]

    if not media:
        del user_sessions[user.id]
        return await update.message.reply_text("⚠️ No media or text received, nothing saved.")

    replies[keyword] = media
    save_replies()
    del user_sessions[user.id]
    await update.message.reply_text(f"✅ Reply for *'{keyword}'* saved successfully!", parse_mode="Markdown")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in user_sessions:
        return

    session = user_sessions[user.id]
    media_entry = {}

    if update.message.photo:
        media_entry = {"type": "photo", "file_id": update.message.photo[-1].file_id}
    elif update.message.video:
        media_entry = {"type": "video", "file_id": update.message.video.file_id}
    elif update.message.animation:  # GIF support
        media_entry = {"type": "animation", "file_id": update.message.animation.file_id}
    elif update.message.audio:
        media_entry = {"type": "audio", "file_id": update.message.audio.file_id}
    elif update.message.document:
        media_entry = {"type": "document", "file_id": update.message.document.file_id}
    elif update.message.text:
        media_entry = {"type": "text", "text": update.message.text}

    if media_entry:
        session["media"].append(media_entry)
        await update.message.reply_text("📥 Added to reply list.")

# === Admin: Delete or list replies ===
async def deletereply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not await is_admin(user, chat):
        return await update.message.reply_text("🚫 Only admins can delete replies.")
    if len(context.args) == 0:
        return await update.message.reply_text("Usage: `/deletereply <keyword>`", parse_mode="Markdown")

    keyword = " ".join(context.args).lower()
    if keyword in replies:
        del replies[keyword]
        save_replies()
        await update.message.reply_text(f"🗑️ Deleted reply for *'{keyword}'*.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ No such keyword found.")

async def listreplies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not replies:
        await update.message.reply_text("📭 No replies configured yet.")
    else:
        msg = "🗂️ *Configured Keywords:*\n" + "\n".join([f"- {k}" for k in replies.keys()])
        await update.message.reply_text(msg, parse_mode="Markdown")

# === Respond to user messages ===
async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat
    user = update.effective_user

    # Ensure bot is mentioned in group messages
    if chat.type in ["group", "supergroup"] and context.bot.username.lower() not in message.text.lower():
        return

    # Cooldown check
    last_time = last_user_message_time.get(user.id)
    if last_time and datetime.now() - last_time < timedelta(seconds=COOLDOWN_SECONDS):
        return await message.reply_text(f"⏳ Please wait {COOLDOWN_SECONDS}s before sending next message.")
    last_user_message_time[user.id] = datetime.now()

    text = message.text.replace(f"@{context.bot.username}", "").strip().lower()
    matched = next((key for key in replies if key in text), None)
    if not matched:
        return

    reply_items = replies[matched]
    media_groups = {"photo": [], "video": [], "animation": [], "audio": [], "document": []}

    for item in reply_items:
        t = item["type"]
        if t == "photo":
            media_groups["photo"].append(InputMediaPhoto(item["file_id"]))
        elif t == "video":
            media_groups["video"].append(InputMediaVideo(item["file_id"]))
        elif t == "animation":
            media_groups["animation"].append(InputMediaAnimation(item["file_id"]))
        elif t == "audio":
            media_groups["audio"].append(InputMediaAudio(item["file_id"]))
        elif t == "document":
            media_groups["document"].append(InputMediaDocument(item["file_id"]))
        elif t == "text":
            await message.reply_text(item["text"])

    # Send grouped media (if any)
    for t, group in media_groups.items():
        if len(group) == 1:
            await message.reply_media_group([group[0]])
        elif group:
            await message.reply_media_group(group)

# === Main ===
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("setreply", setreply))
app.add_handler(CommandHandler("done", done))
app.add_handler(CommandHandler("deletereply", deletereply))
app.add_handler(CommandHandler("listreplies", listreplies))
app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_media))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), respond))

print("🚀 Bot is running...")
app.run_polling()

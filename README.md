# Telegram Group Management Bot 🤖

A lightweight, admin-configurable bot to manage Telegram groups or channels.  
It supports automatic replies, media sharing, keyword-based responses, greetings, and admin-only controls.

---

## 🚀 Features
✅ Dynamic setup directly from Telegram — no coding required  
✅ Media auto-replies (photos, videos, files, text)  
✅ Multiple keyword triggers & aliases  
✅ Inline preview & delete buttons  
✅ Export/Import configuration  
✅ Welcome new members  
✅ Admin-only protection

---

## 🧩 Commands

| Command | Description |
|----------|--------------|
| `/start` | Verify bot is online |
| `/setwelcome <message>` | Set welcome message for new members |
| `/setreply <keyword>` | Start adding media/text for a keyword |
| `/done` | Finish adding items and save reply |
| `/addalias <keyword> <aliases>` | Add alternative trigger words |
| `/listreplies` | List saved replies with preview/delete buttons |
| `/deletereply <keyword>` | Delete a saved keyword manually |
| `/exportreplies` | Export all replies to JSON |
| `/importreplies` | Import replies from JSON |
| (Auto) | Sends saved media when user types a matching keyword |

---

## 🔧 Setup Instructions

1. **Create a Bot**
    - Go to [@BotFather](https://t.me/BotFather)
    - Run `/newbot`
    - Copy your bot token

2. **Get your Telegram User ID**
    - Message [@userinfobot](https://t.me/userinfobot)
    - Note your numeric ID and replace in `ADMINS = [123456789]`

3. **Install dependencies**
   ```bash
   pip install python-telegram-bot==20.8

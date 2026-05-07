import sqlite3, qrcode, time, urllib.parse, asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# ===== CONFIGURATION =====
OWNER_ID = 6999434430
OWNER_USERNAME = "OWNEROFBOTS"

TOKEN_SELLING = "8661796332:AAGRviRUS41H3dck86PM2OX5EUN2e8bVsUs"
TOKEN_DEMO = "8786727671:AAEQC1CKjOQPidrt_Dd497A66fGNoLjai0k"
TOKEN_PRIVATE = "8284255208:AAGrQQfgLzXSgrwD8zsbEuLFdlrq94_OMNk"

# ===== DATABASE =====
conn = sqlite3.connect("shared.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expiry INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT, price INTEGER, expiry_days INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS demo_videos (file_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (file_id TEXT)")
conn.commit()

user_state = {}
user_selected = {}
upload_mode = {} # To track which bot is in upload mode

def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    return res[0] if res else ""

# --- DELETE FUNCTION FOR DEMO ---
def delete_msg(context):
    job = context.job
    try:
        context.bot.delete_message(job.context['chat_id'], job.context['message_id'])
    except: pass

# ==========================
# 1. SELLING BOT HANDLERS
# ==========================
def start_selling(update, context):
    cur.execute("SELECT * FROM products")
    data = cur.fetchall()
    keyboard = [[InlineKeyboardButton(p[1], callback_data=p[0])] for p in data]
    keyboard.append([InlineKeyboardButton("🎬 Demo", url="https://t.me/demovideogiverbot")])
    keyboard.append([InlineKeyboardButton("📞 Support", url=f"https://t.me/{OWNER_USERNAME}")])
    text = get_setting("welcome_text") or "🔥 Welcome! Choose Product 👇"
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def admin_panel(update, context):
    if update.message.from_user.id != OWNER_ID: return
    kb = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("💳 Change UPI", callback_data="admin_upi")],
        [InlineKeyboardButton("✏️ Welcome Text", callback_data="admin_text")]
    ]
    update.message.reply_text("🛠 Admin Control Panel", reply_markup=InlineKeyboardMarkup(kb))

# ==========================
# 2. DEMO BOT HANDLERS
# ==========================
def start_demo(update, context):
    cur.execute("SELECT file_id FROM demo_videos")
    vids = cur.fetchall()
    if not vids:
        update.message.reply_text("No demo videos available.")
        return
    
    for v in vids:
        msg = update.message.reply_video(v[0])
        # Auto-delete after 30 seconds
        context.job_queue.run_once(delete_msg, 30, context={'chat_id': msg.chat_id, 'message_id': msg.message_id})
    
    kb = [[InlineKeyboardButton("🛒 Purchase Premium", url="https://t.me/no1sellerbot")]]
    update.message.reply_text("Videos will delete in 30s.", reply_markup=InlineKeyboardMarkup(kb))

# ==========================
# 3. PRIVATE BOT HANDLERS
# ==========================
def start_private(update, context):
    uid = update.message.from_user.id
    cur.execute("SELECT expiry FROM users WHERE user_id=?", (uid,))
    res = cur.fetchone()
    
    if not res or int(time.time()) > res[0]:
        kb = [[InlineKeyboardButton("🛒 Buy Access", url="https://t.me/no1sellerbot")]]
        update.message.reply_text("❌ No Active Subscription!", reply_markup=InlineKeyboardMarkup(kb))
        return

    cur.execute("SELECT file_id FROM videos")
    vids = cur.fetchall()
    for v in vids:
        update.message.reply_video(v[0], protect_content=True)

# ==========================
# UPLOAD SYSTEM (Common for Demo & Private)
# ==========================
def set_upload(update, context):
    if update.message.from_user.id != OWNER_ID: return
    bot_token = context.bot.token
    upload_mode[update.message.from_user.id] = bot_token
    update.message.reply_text("📤 Upload Mode ON! Now send videos one by one.")

def save_video(update, context):
    uid = update.message.from_user.id
    if uid != OWNER_ID or uid not in upload_mode: return
    
    file_id = update.message.video.file_id
    current_bot = upload_mode[uid]

    if current_bot == TOKEN_DEMO:
        cur.execute("INSERT INTO demo_videos VALUES (?)", (file_id,))
        update.message.reply_text("✅ Saved to Demo Bot")
    elif current_bot == TOKEN_PRIVATE:
        cur.execute("INSERT INTO videos VALUES (?)", (file_id,))
        update.message.reply_text("✅ Saved to Private Bot")
    conn.commit()

def done_upload(update, context):
    uid = update.message.from_user.id
    if uid in upload_mode:
        del upload_mode[uid]
        update.message.reply_text("✅ Upload Mode OFF.")

# (Add other shared functions like admin_buttons, handle_text, product_click here...)
# [Bhai, space ki wajah se baaki shared logic (admin/verify) pichle code jaisa hi use karna]

def main():
    # SELLING BOT
    u1 = Updater(TOKEN_SELLING, use_context=True)
    u1.dispatcher.add_handler(CommandHandler("start", start_selling))
    u1.dispatcher.add_handler(CommandHandler("admin", admin_panel))
    # ... add selling bot's callback/message handlers here ...

    # DEMO BOT
    u2 = Updater(TOKEN_DEMO, use_context=True)
    u2.dispatcher.add_handler(CommandHandler("start", start_demo))
    u2.dispatcher.add_handler(CommandHandler("set", set_upload))
    u2.dispatcher.add_handler(CommandHandler("done", done_upload))
    u2.dispatcher.add_handler(MessageHandler(Filters.video, save_video))

    # PRIVATE BOT
    u3 = Updater(TOKEN_PRIVATE, use_context=True)
    u3.dispatcher.add_handler(CommandHandler("start", start_private))
    u3.dispatcher.add_handler(CommandHandler("set", set_upload))
    u3.dispatcher.add_handler(CommandHandler("done", done_upload))
    u3.dispatcher.add_handler(MessageHandler(Filters.video, save_video))

    u1.start_polling()
    u2.start_polling()
    u3.start_polling()
    u1.idle()

if __name__ == "__main__":
    main()

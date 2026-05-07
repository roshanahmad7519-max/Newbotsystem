import sqlite3, qrcode, time, urllib.parse, asyncio
from telegram import *
from telegram.ext import *

# ===== CONFIGURATION =====
OWNER_ID = 6999434430
OWNER_USERNAME = "OWNEROFBOTS"

TOKEN_SELLING = "8661796332:AAGRviRUS41H3dck86PM2OX5EUN2e8bVsUs"
TOKEN_DEMO = "8786727671:AAEQC1CKjOQPidrt_Dd497A66fGNoLjai0k"
TOKEN_PRIVATE = "8284255208:AAGrQQfgLzXSgrwD8zsbEuLFdlrq94_OMNk"

# ===== DATABASE SETUP =====
conn = sqlite3.connect("shared.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expiry INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT, price INTEGER, expiry_days INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS demo_videos (file_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS videos (file_id TEXT)")

cur.execute("INSERT OR IGNORE INTO settings VALUES ('upi','yourupi@upi')")
cur.execute("INSERT OR IGNORE INTO settings VALUES ('welcome_text','🔥 Welcome! Choose Product 👇')")
conn.commit()

# Shared States
user_selected = {}
user_state = {}
upload_mode = {}

# --- HELPER FUNCTIONS ---
def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    return res[0] if res else ""

async def delete_msg(context, cid, mid):
    await asyncio.sleep(30)
    try: await context.bot.delete_message(cid, mid)
    except: pass

# ==========================
# 1. SELLING BOT LOGIC
# ==========================
async def start_selling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM products")
    data = cur.fetchall()
    keyboard = [[InlineKeyboardButton(p[1], callback_data=p[0])] for p in data]
    keyboard.append([InlineKeyboardButton("🎬 Demo", url="https://t.me/demovideogiverbot")])
    keyboard.append([InlineKeyboardButton("📞 Support", url=f"https://t.me/{OWNER_USERNAME}")])
    
    text = get_setting("welcome_text")
    photo = get_setting("welcome_photo")
    
    if photo:
        await update.message.reply_photo(photo=photo, caption=text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def product_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cur.execute("SELECT * FROM products WHERE id=?", (q.data,))
    p = cur.fetchone()
    if not p: return
    
    upi_link = f"upi://pay?pa={get_setting('upi')}&pn=Shop&am={p[2]}&cu=INR&tn={urllib.parse.quote(p[1])}"
    qrcode.make(upi_link).save(f"{q.data}.png")
    user_selected[q.from_user.id] = q.data
    
    await q.message.reply_photo(photo=open(f"{q.data}.png", "rb"), caption=f"💰 Pay ₹{p[2]}", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify", callback_data="verify")]]))

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    pid = user_selected.get(user.id)
    if not pid: return
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}"), 
           InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")]]
    
    await context.bot.send_photo(chat_id=OWNER_ID, photo=update.message.photo[-1].file_id,
                               caption=f"User: {user.id}\nProduct: {p[1]}\nPrice: ₹{p[2]}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ Screenshot Sent! Waiting for Admin approval.")

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data.split("_")
    uid = int(data[1])
    
    if data[0] == "app":
        pid = user_selected.get(uid)
        cur.execute("SELECT expiry_days FROM products WHERE id=?", (pid,))
        days = cur.fetchone()[0]
        expiry = int(time.time()) + (days * 86400)
        cur.execute("INSERT OR REPLACE INTO users VALUES (?,?)", (uid, expiry))
        conn.commit()
        await context.bot.send_message(uid, "✅ Payment Approved! Access: https://t.me/highqualityvideobot")
        await q.message.edit_caption("✅ User Approved")
    else:
        await context.bot.send_message(uid, "❌ Fake Screenshot! Payment not received.")
        await q.message.edit_caption("❌ User Rejected")

# ==========================
# 2. DEMO BOT LOGIC
# ==========================
async def start_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT file_id FROM demo_videos")
    vids = cur.fetchall()
    for v in vids:
        msg = await update.message.reply_video(v[0], protect_content=True)
        asyncio.create_task(delete_msg(context, msg.chat_id, msg.message_id))
    
    kb = [[InlineKeyboardButton("🛒 Buy Full Videos", url="https://t.me/no1sellerbot")]]
    await update.message.reply_text("Watch demos. They auto-delete in 30s.", reply_markup=InlineKeyboardMarkup(kb))

# ==========================
# 3. PRIVATE BOT LOGIC
# ==========================
async def start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    cur.execute("SELECT expiry FROM users WHERE user_id=?", (uid,))
    res = cur.fetchone()
    
    if not res or int(time.time()) > res[0]:
        await update.message.reply_text("❌ No Access! Buy from @no1sellerbot")
        return

    cur.execute("SELECT file_id FROM videos")
    for v in cur.fetchall():
        await update.message.reply_video(v[0], protect_content=True)

# ===== MAIN RUNNER =====
def main():
    # Selling Bot
    app_sell = Application.builder().token(TOKEN_SELLING).build()
    app_sell.add_handler(CommandHandler("start", start_selling))
    app_sell.add_handler(CallbackQueryHandler(admin_actions, pattern="^(app_|rej_)"))
    app_sell.add_handler(CallbackQueryHandler(product_click, pattern="^(?!verify|app_|rej_)"))
    app_sell.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.message.reply_text("Bhejo screenshot"), pattern="verify"))
    app_sell.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))

    # Demo Bot
    app_demo = Application.builder().token(TOKEN_DEMO).build()
    app_demo.add_handler(CommandHandler("start", start_demo))

    # Private Bot
    app_priv = Application.builder().token(TOKEN_PRIVATE).build()
    app_priv.add_handler(CommandHandler("start", start_private))

    # Run All
    print("Bots are starting...")
    loop = asyncio.get_event_loop()
    loop.create_task(app_sell.run_polling())
    loop.create_task(app_demo.run_polling())
    app_priv.run_polling()

if __name__ == "__main__":
    main()

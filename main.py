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

user_selected = {}

# --- HELPER ---
def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    return res[0] if res else ""

# ==========================
# LOGIC FUNCTIONS
# ==========================
async def start_selling(update, context):
    cur.execute("SELECT * FROM products")
    data = cur.fetchall()
    keyboard = [[InlineKeyboardButton(p[1], callback_data=p[0])] for p in data]
    keyboard.append([InlineKeyboardButton("🎬 Demo", url="https://t.me/demovideogiverbot")])
    keyboard.append([InlineKeyboardButton("📞 Support", url=f"https://t.me/{OWNER_USERNAME}")])
    text = get_setting("welcome_text")
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def product_click(update, context):
    q = update.callback_query
    await q.answer()
    cur.execute("SELECT * FROM products WHERE id=?", (q.data,))
    p = cur.fetchone()
    if not p: return
    upi_link = f"upi://pay?pa={get_setting('upi')}&pn=Shop&am={p[2]}&cu=INR&tn={urllib.parse.quote(p[1])}"
    qrcode.make(upi_link).save(f"qr_{q.from_user.id}.png")
    user_selected[q.from_user.id] = q.data
    await q.message.reply_photo(photo=open(f"qr_{q.from_user.id}.png", "rb"), caption=f"💰 Pay ₹{p[2]}", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify", callback_data="verify")]]))

async def screenshot_handler(update, context):
    user = update.message.from_user
    pid = user_selected.get(user.id)
    if not pid: return
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")]]
    await context.bot.send_photo(chat_id=OWNER_ID, photo=update.message.photo[-1].file_id, caption=f"ID: {user.id}\nAmt: ₹{p[2]}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("Sent! Wait for Admin.")

async def admin_verify(update, context):
    q = update.callback_query
    data = q.data.split("_")
    uid = int(data[1])
    if data[0] == "app":
        pid = user_selected.get(uid)
        cur.execute("SELECT expiry_days FROM products WHERE id=?", (pid,))
        days = cur.fetchone()[0]
        expiry = int(time.time()) + (days * 86400)
        cur.execute("INSERT OR REPLACE INTO users VALUES (?,?)", (uid, expiry))
        conn.commit()
        await context.bot.send_message(uid, "✅ Approved! Link: https://t.me/highqualityvideobot")
    else:
        await context.bot.send_message(uid, "❌ Rejected! Send Real Payment Screenshot.")
    await q.message.delete()

async def start_demo(update, context):
    cur.execute("SELECT file_id FROM demo_videos")
    for v in cur.fetchall():
        await update.message.reply_video(v[0])

async def start_private(update, context):
    uid = update.message.from_user.id
    cur.execute("SELECT expiry FROM users WHERE user_id=?", (uid,))
    res = cur.fetchone()
    if not res or int(time.time()) > res[0]:
        await update.message.reply_text("❌ Buy Premium @no1sellerbot")
        return
    cur.execute("SELECT file_id FROM videos")
    for v in cur.fetchall():
        await update.message.reply_video(v[0], protect_content=True)

# ==========================
# MULTI-BOT RUNNER
# ==========================
async def run_bots():
    # 1. Selling Bot
    app_sell = Application.builder().token(TOKEN_SELLING).build()
    app_sell.add_handler(CommandHandler("start", start_selling))
    app_sell.add_handler(CallbackQueryHandler(admin_verify, pattern="^(app_|rej_)"))
    app_sell.add_handler(CallbackQueryHandler(product_click, pattern="^(?!verify|app_|rej_)"))
    app_sell.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))

    # 2. Demo Bot
    app_demo = Application.builder().token(TOKEN_DEMO).build()
    app_demo.add_handler(CommandHandler("start", start_demo))

    # 3. Private Bot
    app_priv = Application.builder().token(TOKEN_PRIVATE).build()
    app_priv.add_handler(CommandHandler("start", start_private))

    # Start All
    await app_sell.initialize()
    await app_demo.initialize()
    await app_priv.initialize()
    
    await app_sell.updater.start_polling()
    await app_demo.updater.start_polling()
    await app_priv.updater.start_polling()
    
    await app_sell.start()
    await app_demo.start()
    await app_priv.start()

    print("--- Teeno Bots Online Hain! ---")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_bots())

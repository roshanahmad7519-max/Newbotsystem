import sqlite3, qrcode, time, urllib.parse, asyncio
from telegram import *
from telegram.ext import *

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

def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    return res[0] if res else ""

# ===== SELLING BOT HANDLERS =====
async def start_selling(update, context):
    cur.execute("SELECT * FROM products")
    data = cur.fetchall()
    keyboard = [[InlineKeyboardButton(p[1], callback_data=p[0])] for p in data]
    keyboard.append([InlineKeyboardButton("🎬 Demo", url="https://t.me/demovideogiverbot")])
    keyboard.append([InlineKeyboardButton("📞 Support", url=f"https://t.me/{OWNER_USERNAME}")])
    text = get_setting("welcome_text") or "🔥 Welcome! Choose Product 👇"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_panel(update, context):
    if update.message.from_user.id != OWNER_ID: return
    kb = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add")],
        [InlineKeyboardButton("💳 Change UPI", callback_data="admin_upi")],
        [InlineKeyboardButton("✏️ Welcome Text", callback_data="admin_text")]
    ]
    await update.message.reply_text("🛠 Admin Control Panel", reply_markup=InlineKeyboardMarkup(kb))

async def admin_buttons(update, context):
    q = update.callback_query
    await q.answer()
    user_state[q.from_user.id] = q.data
    if q.data == "admin_add":
        await q.message.reply_text("Format bhejo: `ID Naam Price Days` \n(Ex: p1 GoldPack 499 30)")
    elif q.data == "admin_upi":
        await q.message.reply_text("Naya UPI ID bhejo:")
    elif q.data == "admin_text":
        await q.message.reply_text("Naya Welcome Text bhejo:")

async def handle_text(update, context):
    uid = update.message.from_user.id
    state = user_state.get(uid)
    if not state or uid != OWNER_ID: return

    if state == "admin_add":
        try:
            pid, name, price, days = update.message.text.split()
            cur.execute("INSERT INTO products VALUES (?,?,?,?)", (pid, name, int(price), int(days)))
            conn.commit()
            await update.message.reply_text("✅ Product Added!")
        except: await update.message.reply_text("❌ Galat format! Try again.")
    
    elif state == "admin_upi":
        cur.execute("INSERT OR REPLACE INTO settings VALUES ('upi',?)", (update.message.text,))
        conn.commit()
        await update.message.reply_text("✅ UPI Updated!")

    elif state == "admin_text":
        cur.execute("INSERT OR REPLACE INTO settings VALUES ('welcome_text',?)", (update.message.text,))
        conn.commit()
        await update.message.reply_text("✅ Text Updated!")
    
    user_state[uid] = None

# (Baaki Functions like product_click, screenshot_handler, admin_verify same rahenge)
async def product_click(update, context):
    q = update.callback_query
    if q.data.startswith("admin_"): return
    await q.answer()
    cur.execute("SELECT * FROM products WHERE id=?", (q.data,))
    p = cur.fetchone()
    if not p: return
    upi = get_setting("upi") or "test@upi"
    upi_link = f"upi://pay?pa={upi}&pn=Shop&am={p[2]}&cu=INR&tn={p[1]}"
    qrcode.make(upi_link).save(f"qr_{q.from_user.id}.png")
    user_selected[q.from_user.id] = q.data
    await q.message.reply_photo(photo=open(f"qr_{q.from_user.id}.png", "rb"), caption=f"💰 Pay ₹{p[2]} for {p[1]}", 
                               reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify", callback_data="verify")]]))

async def screenshot_handler(update, context):
    user = update.message.from_user
    pid = user_selected.get(user.id)
    if not pid: return
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")]]
    await context.bot.send_photo(chat_id=OWNER_ID, photo=update.message.photo[-1].file_id, caption=f"User: {user.id}\nProduct: {p[1]}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ Screenshot Sent! Please wait.")

async def admin_verify(update, context):
    q = update.callback_query
    data = q.data.split("_")
    uid = int(data[1])
    if data[0] == "app":
        pid = user_selected.get(uid)
        cur.execute("SELECT expiry_days FROM products WHERE id=?", (pid,))
        res = cur.fetchone()
        days = res[0] if res else 30
        expiry = int(time.time()) + (days * 86400)
        cur.execute("INSERT OR REPLACE INTO users VALUES (?,?)", (uid, expiry))
        conn.commit()
        await context.bot.send_message(uid, "✅ Payment Approved! Access: https://t.me/highqualityvideobot")
    else:
        await context.bot.send_message(uid, "❌ Fake Screenshot! Contact Support.")
    await q.message.delete()

# ===== RUNNER =====
async def run_bots():
    app_sell = Application.builder().token(TOKEN_SELLING).build()
    app_sell.add_handler(CommandHandler("start", start_selling))
    app_sell.add_handler(CommandHandler("admin", admin_panel))
    app_sell.add_handler(CallbackQueryHandler(admin_buttons, pattern="^admin_"))
    app_sell.add_handler(CallbackQueryHandler(admin_verify, pattern="^(app_|rej_)"))
    app_sell.add_handler(CallbackQueryHandler(product_click))
    app_sell.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))
    app_sell.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app_demo = Application.builder().token(TOKEN_DEMO).build()
    app_demo.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Demo Bot Online")))

    app_priv = Application.builder().token(TOKEN_PRIVATE).build()
    app_priv.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Private Bot Online")))

    await app_sell.initialize()
    await app_demo.initialize()
    await app_priv.initialize()
    await app_sell.updater.start_polling()
    await app_demo.updater.start_polling()
    await app_priv.updater.start_polling()
    await app_sell.start()
    await app_demo.start()
    await app_priv.start()

    while True: await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_bots())

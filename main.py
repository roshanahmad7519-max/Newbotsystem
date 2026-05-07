import sqlite3, qrcode, time, urllib.parse
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

def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cur.fetchone()
    return res[0] if res else ""

# ===== HANDLERS =====
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

def admin_buttons(update, context):
    q = update.callback_query
    q.answer()
    user_state[q.from_user.id] = q.data
    if q.data == "admin_add":
        q.message.reply_text("Bhejo: `ID Naam Price Days` (p1 Pack 499 30)")
    elif q.data == "admin_upi":
        q.message.reply_text("Naya UPI ID bhejo:")
    elif q.data == "admin_text":
        q.message.reply_text("Naya Welcome Text bhejo:")

def handle_text(update, context):
    uid = update.message.from_user.id
    state = user_state.get(uid)
    if not state or uid != OWNER_ID: return

    if state == "admin_add":
        try:
            pid, name, price, days = update.message.text.split()
            cur.execute("INSERT INTO products VALUES (?,?,?,?)", (pid, name, int(price), int(days)))
            conn.commit()
            update.message.reply_text("✅ Product Added!")
        except: update.message.reply_text("❌ Format galat hai.")
    elif state == "admin_upi":
        cur.execute("INSERT OR REPLACE INTO settings VALUES ('upi',?)", (update.message.text,))
        conn.commit()
        update.message.reply_text("✅ UPI Updated!")
    elif state == "admin_text":
        cur.execute("INSERT OR REPLACE INTO settings VALUES ('welcome_text',?)", (update.message.text,))
        conn.commit()
        update.message.reply_text("✅ Text Updated!")
    user_state[uid] = None

def product_click(update, context):
    q = update.callback_query
    if q.data.startswith("admin_") or q.data.startswith("app_") or q.data.startswith("rej_"): return
    if q.data == "verify":
        q.message.reply_text("📸 Screenshot bhejo payment ka.")
        return
    q.answer()
    cur.execute("SELECT * FROM products WHERE id=?", (q.data,))
    p = cur.fetchone()
    if not p: return
    upi = get_setting("upi") or "test@upi"
    upi_link = f"upi://pay?pa={upi}&pn=Shop&am={p[2]}&cu=INR&tn={p[1]}"
    qrcode.make(upi_link).save(f"qr_{q.from_user.id}.png")
    user_selected[q.from_user.id] = q.data
    q.message.reply_photo(photo=open(f"qr_{q.from_user.id}.png", "rb"), caption=f"💰 Pay ₹{p[2]} for {p[1]}", 
                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Verify", callback_data="verify")]]))

def screenshot_handler(update, context):
    user = update.message.from_user
    pid = user_selected.get(user.id)
    if not pid: return
    cur.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cur.fetchone()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")]]
    context.bot.send_photo(chat_id=OWNER_ID, photo=update.message.photo[-1].file_id, caption=f"User: {user.id}\nProd: {p[1]}", reply_markup=InlineKeyboardMarkup(kb))
    update.message.reply_text("✅ Screenshot Sent! Wait for Admin.")

def admin_verify(update, context):
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
        context.bot.send_message(uid, "✅ Approved! Link: https://t.me/highqualityvideobot")
    else:
        context.bot.send_message(uid, "❌ Rejected! Send Real Payment.")
    q.message.delete()

# ===== MAIN =====
def main():
    # Selling Bot
    u1 = Updater(TOKEN_SELLING, use_context=True)
    dp1 = u1.dispatcher
    dp1.add_handler(CommandHandler("start", start_selling))
    dp1.add_handler(CommandHandler("admin", admin_panel))
    dp1.add_handler(CallbackQueryHandler(admin_buttons, pattern="^admin_"))
    dp1.add_handler(CallbackQueryHandler(admin_verify, pattern="^(app_|rej_)"))
    dp1.add_handler(CallbackQueryHandler(product_click))
    dp1.add_handler(MessageHandler(Filters.photo, screenshot_handler))
    dp1.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    # Demo Bot (Placeholder)
    u2 = Updater(TOKEN_DEMO, use_context=True)
    u2.dispatcher.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Demo Bot Online")))

    # Private Bot (Placeholder)
    u3 = Updater(TOKEN_PRIVATE, use_context=True)
    u3.dispatcher.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Private Bot Online")))

    u1.start_polling()
    u2.start_polling()
    u3.start_polling()
    print("--- Bots are Online ---")
    u1.idle()

if __name__ == "__main__":
    main()

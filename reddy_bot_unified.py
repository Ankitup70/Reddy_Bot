# Complete code with polling method (no webhook needed)
# Paste this in your reddy_bot_unified.py

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random, string, datetime, threading, time, os, json, sqlite3, qrcode, io, requests
from flask import Flask, request, jsonify, send_from_directory

# ========== CONFIG ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"
DB_FILE = "bot_data.db"
UPI_ID = "q542401897@ybl"
UPIGATEWAY_API_KEY = "3712981c-6df2-490c-af03-66bd0ec43b88"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, username TEXT, keys_data TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, product TEXT, duration TEXT, amount INTEGER, key TEXT, date TEXT, payment_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keys_pool (product TEXT, duration TEXT, key TEXT, added_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_orders', 0)")
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_revenue', 0)")
    conn.commit()
    conn.close()
init_db()

def get_stock(product, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM keys_pool WHERE product=? AND duration=?", (product, duration))
    count = c.fetchone()[0]
    conn.close()
    return count

def pop_key(product, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key FROM keys_pool WHERE product=? AND duration=? LIMIT 1", (product, duration))
    row = c.fetchone()
    if row:
        key = row[0]
        c.execute("DELETE FROM keys_pool WHERE product=? AND duration=? AND key=?", (product, duration, key))
        conn.commit()
        conn.close()
        return key
    conn.close()
    return None

def add_keys_to_db(product, duration, key_list):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for k in key_list:
        c.execute("INSERT INTO keys_pool (product, duration, key, added_date) VALUES (?,?,?,?)", (product, duration, k, now))
    conn.commit()
    conn.close()

def save_user_key(user_id, username, product_name, duration, key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT keys_data FROM users WHERE user_id=?", (str(user_id),))
    row = c.fetchone()
    keys_list = json.loads(row[0]) if row else []
    keys_list.append({
        "product": product_name,
        "duration": duration,
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    })
    c.execute("INSERT OR REPLACE INTO users (user_id, username, keys_data) VALUES (?,?,?)",
              (str(user_id), username, json.dumps(keys_list)))
    conn.commit()
    conn.close()

def save_order(order_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO orders (username, product, duration, amount, key, date, payment_id) VALUES (?,?,?,?,?,?,?)",
              (order_data['username'], order_data['product'], order_data['duration'],
               order_data['amount'], order_data['key'], order_data['date'], order_data.get('payment_id', '')))
    c.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_orders'")
    c.execute("UPDATE stats SET value = value + ? WHERE key = 'total_revenue'", (order_data['amount'],))
    conn.commit()
    conn.close()

def generate_key(prefix):
    return f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"

PRODUCTS = {
    "deadeye": {"name": "Deadeye", "emoji": "🎯"},
    "vision": {"name": "Vision", "emoji": "👁️"},
    "rage": {"name": "Rage", "emoji": "⚡"},
    "winios": {"name": "WinIOS", "emoji": "💻"},
    "kingios": {"name": "KingIOS", "emoji": "👑"},
}
PRICES = {
    "deadeye": {"day": 149, "week": 699, "month": 1299},
    "vision": {"day": 199, "week": 699, "month": 2200},
    "rage": {"day": 149, "week": 699, "month": 1299},
    "winios": {"day": 149, "week": 599, "month": 999},
    "kingios": {"day": 199, "week": 699, "month": 2200},
}
PREFIX = {
    "deadeye": "DEAD",
    "vision": "VIS",
    "rage": "RAGE",
    "winios": "WIN",
    "kingios": "KING",
}

def make_qr(amount, order_id):
    upi = f"upi://pay?pa={UPI_ID}&pn=Reddy+Premium&am={amount}&tn={order_id}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ========== KEYBOARDS ==========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🛒 Buy Now", callback_data="buy", style='success'),
           InlineKeyboardButton("🔑 My Keys", callback_data="mykeys", style='primary'),
           InlineKeyboardButton("📦 Stock", callback_data="stock", style='primary'),
           InlineKeyboardButton("💬 Support", callback_data="help", style='primary'))
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        total = get_stock(key, "day") + get_stock(key, "week") + get_stock(key, "month")
        style = 'success' if total > 0 else 'danger'
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"prod_{key}", style=style))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
    return kb

def plans_kb(product):
    kb = InlineKeyboardMarkup(row_width=1)
    p = PRICES[product]
    day_stock, week_stock, month_stock = get_stock(product, "day"), get_stock(product, "week"), get_stock(product, "month")
    day_style = 'success' if day_stock > 0 else 'danger'
    week_style = 'success' if week_stock > 0 else 'danger'
    month_style = 'success' if month_stock > 0 else 'danger'
    kb.add(InlineKeyboardButton(f"📅 1 Day - ₹{p['day']}" + (" 🔴" if day_stock == 0 else ""), callback_data=f"plan_{product}_day", style=day_style))
    kb.add(InlineKeyboardButton(f"📅 7 Days - ₹{p['week']}" + (" 🔴" if week_stock == 0 else ""), callback_data=f"plan_{product}_week", style=week_style))
    kb.add(InlineKeyboardButton(f"📅 30 Days - ₹{p['month']}" + (" 🔴" if month_stock == 0 else ""), callback_data=f"plan_{product}_month", style=month_style))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
    return kb

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, f"👑 *REDDY PREMIUM*\n\nHello {msg.from_user.first_name}!\n\n👇 Choose option", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid, uid, uname = call.message.chat.id, call.from_user.id, call.from_user.username or "User"
    data = call.data
    if data == "back":
        bot.edit_message_text("👇 *Main Menu*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "buy":
        bot.edit_message_text("🛒 *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    elif data == "stock":
        text = "📦 *Stock*\n\n" + "\n".join([f"{p['emoji']} {p['name']}: 1D:{get_stock(key,'day')} 7D:{get_stock(key,'week')} 30D:{get_stock(key,'month')}" for key, p in PRODUCTS.items()])
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "mykeys":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT keys_data FROM users WHERE user_id=?", (str(uid),))
        row = c.fetchone()
        conn.close()
        keys = json.loads(row[0]) if row else []
        if not keys:
            bot.edit_message_text("🔑 *My Keys*\n\nNo keys yet.", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            txt = "🔑 *Your Keys*\n\n" + "\n".join([f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n" for k in keys[-5:][::-1]])
            bot.edit_message_text(txt, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack", style='primary'), InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
        bot.edit_message_text("💬 *Support*\n\n@ReddyHack\n24/7", cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        bot.edit_message_text(f"{PRODUCTS[product]['emoji']} *{PRODUCTS[product]['name']}*\n👇 Choose plan", cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    elif data.startswith("plan_"):
        _, product, duration = data.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "Sold out!", show_alert=True)
            return
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        pending_orders[order_id] = {"user_id": uid, "username": uname, "product": product, "duration": duration, "amount": amount, "chat_id": cid}
        qr = make_qr(amount, order_id)
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=f"💳 *UPI Payment*\n\nOrder: `{order_id}`\nProduct: {PRODUCTS[product]['name']}\nAmount: ₹{amount}\n\nUPI ID: `{UPI_ID}`\n\nScan QR to pay.\n**Bot will auto-check payment!**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}", style='danger')))
        
        # Polling thread
        def poll():
            for _ in range(24):  # 2 minutes (24 * 5 sec)
                time.sleep(5)
                if order_id not in pending_orders:
                    return
                try:
                    resp = requests.post("https://upigateway.com/api/v1/check-payment", json={"client_txn_id": order_id, "api_key": UPIGATEWAY_API_KEY}, timeout=10)
                    if resp.status_code == 200 and resp.json().get("status") == "success" and resp.json().get("payment_received"):
                        order = pending_orders[order_id]
                        key = pop_key(order['product'], order['duration']) or generate_key(PREFIX.get(order['product'], "KEY"))
                        save_user_key(order['user_id'], order['username'], PRODUCTS[order['product']]['name'], order['duration'], key)
                        save_order({"username": order['username'], "product": PRODUCTS[order['product']]['name'], "duration": order['duration'], "amount": order['amount'], "key": key, "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p"), "payment_id": "upigateway"})
                        bot.send_message(order['chat_id'], f"✅ *Payment Verified!*\n\n🔑 Your Key: `{key}`\n\nThank you!", parse_mode="Markdown")
                        del pending_orders[order_id]
                        return
                except:
                    pass
            if order_id in pending_orders:
                bot.send_message(cid, "⌛ Payment not received. Order expired.", reply_markup=main_menu())
                del pending_orders[order_id]
        threading.Thread(target=poll, daemon=True).start()
    elif data.startswith("cancel_"):
        oid = data.split("_")[1]
        pending_orders.pop(oid, None)
        bot.edit_message_text("❌ Cancelled", cid, call.message.id, reply_markup=main_menu())

# ========== HEALTH CHECK ==========
@app.route('/')
def home():
    return jsonify({"status": "online", "gateway": "upigateway"})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('UTF-8'))])
        return '', 200
    return '', 403

# ========== MAIN ==========
if __name__ == "__main__":
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

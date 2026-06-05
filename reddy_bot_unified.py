#!/usr/bin/env python3
"""
REDDY PREMIUM BOT – SQLite + UPI Auto Verify (SMS Webhook for iOS)
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import string
import datetime
import threading
import time
import os
import json
import re
import sqlite3
import qrcode
import io
from flask import Flask, request, jsonify, send_from_directory

# ========== CONFIG ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"
DB_FILE = "bot_data.db"
UPI_ID = "q542401897@ybl"
SMS_WEBHOOK_SECRET = "MySecretKey123"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}       # order_id -> details
processed_txns = set()    # to avoid duplicate processing

# ========== DATABASE SETUP (SQLite) ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        keys_data TEXT
    )''')
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        product TEXT,
        duration TEXT,
        amount INTEGER,
        key TEXT,
        date TEXT,
        payment_id TEXT
    )''')
    # Keys pool table
    c.execute('''CREATE TABLE IF NOT EXISTS keys_pool (
        product TEXT,
        duration TEXT,
        key TEXT,
        added_date TEXT
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_keys ON keys_pool (product, duration)')
    # Stats table
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        key TEXT PRIMARY KEY,
        value INTEGER
    )''')
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_orders', 0)")
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_revenue', 0)")
    conn.commit()
    conn.close()

init_db()

# ========== DATABASE HELPERS ==========
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
        c.execute("DELETE FROM keys_pool WHERE product=? AND duration=? AND key=? LIMIT 1", (product, duration, key))
        conn.commit()
        conn.close()
        print(f"[POP] {product} {duration} -> {key}")
        return key
    conn.close()
    return None

def add_keys_to_db(product, duration, key_list):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for k in key_list:
        c.execute("INSERT INTO keys_pool (product, duration, key, added_date) VALUES (?,?,?,?)",
                  (product, duration, k, now))
    conn.commit()
    conn.close()
    print(f"[ADD] {product} {duration} -> {len(key_list)} keys")

def save_user_key(user_id, username, product_name, duration, key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT keys_data FROM users WHERE user_id=?", (str(user_id),))
    row = c.fetchone()
    if row:
        keys_list = json.loads(row[0])
    else:
        keys_list = []
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
    c.execute("""INSERT INTO orders (username, product, duration, amount, key, date, payment_id)
                 VALUES (?,?,?,?,?,?,?)""",
              (order_data['username'], order_data['product'], order_data['duration'],
               order_data['amount'], order_data['key'], order_data['date'], order_data.get('payment_id', '')))
    c.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_orders'")
    c.execute("UPDATE stats SET value = value + ? WHERE key = 'total_revenue'", (order_data['amount'],))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM stats WHERE key='total_orders'")
    total_orders = c.fetchone()[0]
    c.execute("SELECT value FROM stats WHERE key='total_revenue'")
    total_revenue = c.fetchone()[0]
    conn.close()
    return {"total_orders": total_orders, "total_revenue": total_revenue}

def get_all_keys():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT product, duration, key FROM keys_pool")
    rows = c.fetchall()
    conn.close()
    keys_dict = {p: {"day": [], "week": [], "month": []} for p in PRODUCTS}
    for product, duration, key in rows:
        if product in keys_dict:
            keys_dict[product][duration].append(key)
    return keys_dict

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, keys_data FROM users")
    rows = c.fetchall()
    conn.close()
    users = {}
    for uid, uname, kdata in rows:
        users[uid] = {"username": uname, "keys": json.loads(kdata) if kdata else []}
    return users

def get_all_orders():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, product, duration, amount, key, date FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [{"username": r[0], "product": r[1], "duration": r[2], "amount": r[3], "key": r[4], "date": r[5]} for r in rows]

def clear_keys_pool(product, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM keys_pool WHERE product=? AND duration=?", (product, duration))
    conn.commit()
    conn.close()

def generate_key(prefix):
    return f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"

# ========== PRODUCTS & PRICES ==========
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
    kb.add(
        InlineKeyboardButton("🛒 Buy Now", callback_data="buy", style='success'),
        InlineKeyboardButton("🔑 My Keys", callback_data="mykeys", style='primary'),
        InlineKeyboardButton("📦 Stock", callback_data="stock", style='primary'),
        InlineKeyboardButton("💬 Support", callback_data="help", style='primary'),
    )
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
    day_stock = get_stock(product, "day")
    week_stock = get_stock(product, "week")
    month_stock = get_stock(product, "month")
    day_style = 'success' if day_stock > 0 else 'danger'
    week_style = 'success' if week_stock > 0 else 'danger'
    month_style = 'success' if month_stock > 0 else 'danger'
    day_btn = f"📅 1 Day - ₹{p['day']}" + (" 🔴" if day_stock == 0 else "")
    week_btn = f"📅 7 Days - ₹{p['week']}" + (" 🔴" if week_stock == 0 else "")
    month_btn = f"📅 30 Days - ₹{p['month']}" + (" 🔴" if month_stock == 0 else "")
    kb.add(InlineKeyboardButton(day_btn, callback_data=f"plan_{product}_day", style=day_style))
    kb.add(InlineKeyboardButton(week_btn, callback_data=f"plan_{product}_week", style=week_style))
    kb.add(InlineKeyboardButton(month_btn, callback_data=f"plan_{product}_month", style=month_style))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
    return kb

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, f"👑 *REDDY PREMIUM*\n\nHello {msg.from_user.first_name}!\n\n💎 Trusted License Shop\n⚡ UPI Auto-Delivery\n🛡️ 100% Genuine\n\n👇 Choose option", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "back":
        bot.edit_message_text("👇 *Main Menu*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "buy":
        bot.edit_message_text("🛒 *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    elif data == "stock":
        text = "📦 *Stock Available*\n\n"
        for key, p in PRODUCTS.items():
            d = get_stock(key, "day")
            w = get_stock(key, "week")
            m = get_stock(key, "month")
            text += f"{p['emoji']} *{p['name']}* : 1D:{d} 7D:{w} 30D:{m}\n"
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
            txt = "🔑 *Your Keys*\n\n"
            for k in keys[-5:][::-1]:
                txt += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            bot.edit_message_text(txt, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack", style='primary'))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
        bot.edit_message_text("💬 *Support*\n\n@ReddyHack\n24/7", cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        bot.edit_message_text(f"{p['emoji']} *{p['name']}*\n👇 Choose plan", cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    elif data.startswith("plan_"):
        _, product, duration = data.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "Sold out!", show_alert=True)
            return
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        qr = make_qr(amount, order_id)
        caption = f"💳 *UPI Payment*\n\nOrder: `{order_id}`\nProduct: {PRODUCTS[product]['name']}\nAmount: ₹{amount}\n\nUPI ID: `{UPI_ID}`\n\nScan QR code or pay to this UPI ID.\nAfter payment, key will be sent automatically."
        bot.delete_message(cid, call.message.id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}", style='danger'))
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=kb)
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_text("❌ Cancelled", cid, call.message.id, reply_markup=main_menu())

def expire_order(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ Order expired. Start fresh.", reply_markup=main_menu())
        except:
            pass

# ========== SMS WEBHOOK (iOS & Android) ==========
@app.route('/sms_webhook_ios', methods=['POST'])
def sms_webhook_ios():
    data = request.json
    if data.get('secret') != SMS_WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    sms_text = data.get('sms_body', '')
    print(f"[DEBUG] iOS webhook received: {sms_text}")
    # Extract amount (supports ₹149, Rs 149, 149, INR149)
    match = re.search(r'[\₹RsINR]*\s*(\d{2,4})', sms_text, re.IGNORECASE)
    amount = int(match.group(1)) if match else 0
    # Find pending order with same amount
    matched = None
    for oid, order in pending_orders.items():
        if order['amount'] == amount:
            matched = oid
            break
    if not matched:
        return jsonify({"error": f"No pending order for amount {amount}"}), 404
    order = pending_orders[matched]
    key = pop_key(order['product'], order['duration'])
    if not key:
        key = generate_key(PREFIX.get(order['product'], "KEY"))
    # Deliver key
    bot.send_message(order['chat_id'],
                     f"✅ *Payment Verified!*\n\n🔑 Your Key: `{key}`\n\nThank you!",
                     parse_mode="Markdown")
    # Save order
    save_order({
        "username": order['username'],
        "product": PRODUCTS[order['product']]['name'],
        "duration": order['duration'],
        "amount": order['amount'],
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p"),
        "payment_id": "ios_webhook"
    })
    del pending_orders[matched]
    return jsonify({"status": "key_delivered", "order_id": matched})

# ========== ADMIN PANEL API ROUTES ==========
@app.route('/')
def home():
    return jsonify({"status": "online", "storage": "sqlite"})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard')
def dashboard():
    stats = get_stats()
    total_keys = sum(get_stock(p, "day") + get_stock(p, "week") + get_stock(p, "month") for p in PRODUCTS)
    total_users = len(get_all_users())
    return jsonify({
        "total_keys": total_keys,
        "total_orders": stats["total_orders"],
        "total_users": total_users,
        "total_revenue": stats["total_revenue"]
    })

@app.route('/api/keys/all')
def keys_all():
    return jsonify(get_all_keys())

@app.route('/api/keys/<product>/<duration>')
def get_keys(product, duration):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key FROM keys_pool WHERE product=? AND duration=?", (product, duration))
    keys = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify({"keys": keys})

@app.route('/api/keys', methods=['POST'])
def add_keys():
    body = request.json
    product = body['product']
    duration = body['duration']
    key_list = body['keys']
    add_keys_to_db(product, duration, key_list)
    return jsonify({"ok": True})

@app.route('/api/keys/generate', methods=['POST'])
def gen_keys():
    body = request.json
    product = body['product']
    duration = body['duration']
    count = body['count']
    prefix = PREFIX.get(product, "KEY")
    new_keys = [generate_key(prefix) for _ in range(count)]
    add_keys_to_db(product, duration, new_keys)
    return jsonify({"ok": True})

@app.route('/api/keys/<product>/<duration>', methods=['DELETE'])
def clear_keys(product, duration):
    clear_keys_pool(product, duration)
    return jsonify({"ok": True})

@app.route('/api/prices')
def get_prices():
    return jsonify(PRICES)

@app.route('/api/prices', methods=['POST'])
def set_prices():
    body = request.json
    PRICES[body['product']] = body['prices']
    return jsonify({"ok": True})

@app.route('/api/orders')
def get_orders():
    return jsonify(get_all_orders())

@app.route('/api/orders', methods=['DELETE'])
def del_orders():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM orders")
    c.execute("UPDATE stats SET value = 0 WHERE key = 'total_orders'")
    c.execute("UPDATE stats SET value = 0 WHERE key = 'total_revenue'")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/users')
def get_users():
    return jsonify(get_all_users())

@app.route('/api/auth', methods=['POST'])
def auth():
    if request.json.get('password') == "reddy2024":
        return jsonify({"token": "ok"})
    return jsonify({"error": "Wrong"}), 401

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('UTF-8'))])
        return '', 200
    return '', 403

# ========== MAIN ==========
if __name__ == "__main__":
    print("Starting Reddy Premium Bot with SQLite + iOS webhook...")
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

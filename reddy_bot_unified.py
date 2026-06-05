#!/usr/bin/env python3
"""
REDDY PREMIUM BOT – UPI AUTO VERIFY (SMS FORWARDER)
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random, string, datetime, threading, time, os, json, re
from flask import Flask, request, jsonify, send_from_directory

# ========== CONFIG (Change these on Render via Env Vars) ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"
DATA_FILE = "bot_data.json"
UPI_ID = "q542401897@ybl"
SMS_WEBHOOK_SECRET = "MySecretKey123"   # ← same as in SMS Forwarder app

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}
processed_txns = set()

# ---------- Data Storage ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {},
        "orders": [],
        "keys": {p: {"day": [], "week": [], "month": []} for p in ["deadeye","vision","rage","winios","kingios"]}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

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

def get_stock(product, duration):
    return len(data["keys"].get(product, {}).get(duration, []))

def pop_key(product, duration):
    pool = data["keys"].get(product, {}).get(duration, [])
    if pool:
        key = pool.pop(0)
        save_data(data)
        return key
    return None

def add_keys_to_db(product, duration, key_list):
    if product not in data["keys"]:
        data["keys"][product] = {"day": [], "week": [], "month": []}
    data["keys"][product][duration].extend(key_list)
    save_data(data)

def save_user_key(user_id, username, product_name, duration, key):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"username": username, "keys": []}
    data["users"][uid]["keys"].append({
        "product": product_name,
        "duration": duration,
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    })
    save_data(data)

def save_order(order_data):
    data["orders"].insert(0, order_data)
    save_data(data)

def generate_key(product):
    prefix = PREFIX.get(product, "KEY")
    return f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"

def make_qr(amount, order_id):
    import qrcode, io
    upi = f"upi://pay?pa={UPI_ID}&pn=Reddy+Premium&am={amount}&tn={order_id}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ---------- Keyboards ----------
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

# ---------- Bot Handlers ----------
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, f"👑 *REDDY PREMIUM*\n\nHello {msg.from_user.first_name}!\n\n💎 Trusted License Shop\n⚡ UPI Auto-Delivery\n🛡️ 100% Genuine\n\n👇 Choose option", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data_cb = call.data

    if data_cb == "back":
        bot.edit_message_text("👇 *Main Menu*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data_cb == "buy":
        bot.edit_message_text("🛒 *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    elif data_cb == "stock":
        text = "📦 *Stock*\n\n"
        for key, p in PRODUCTS.items():
            d,w,m = get_stock(key,"day"), get_stock(key,"week"), get_stock(key,"month")
            text += f"{p['emoji']} {p['name']}: 1D:{d} 7D:{w} 30D:{m}\n"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data_cb == "mykeys":
        user_keys = data["users"].get(str(uid), {}).get("keys", [])
        if not user_keys:
            bot.edit_message_text("🔑 *My Keys*\n\nNo keys yet.", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            txt = "🔑 *Your Keys*\n\n"
            for k in user_keys[-5:][::-1]:
                txt += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            bot.edit_message_text(txt, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    elif data_cb == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack", style='primary'))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
        bot.edit_message_text("💬 *Support*\n\n@ReddyHack\n24/7", cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    elif data_cb.startswith("prod_"):
        product = data_cb.split("_")[1]
        p = PRODUCTS[product]
        bot.edit_message_text(f"{p['emoji']} *{p['name']}*\n👇 Choose plan", cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    elif data_cb.startswith("plan_"):
        _, product, duration = data_cb.split("_")
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
        caption = f"💳 *UPI Payment*\n\nOrder: `{order_id}`\nProduct: {PRODUCTS[product]['name']}\nAmount: ₹{amount}\n\nUPI ID: `{UPI_ID}`\n\n*Scan QR or Pay & SMS will auto-verify*"
        bot.delete_message(cid, call.message.id)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}", style='danger'))
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=kb)
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    elif data_cb.startswith("cancel_"):
        order_id = data_cb.split("_")[1]
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

# ---------- SMS Webhook (UPI Auto Verify) ----------
@app.route('/sms_webhook', methods=['POST'])
def sms_webhook():
    data_json = request.json
    if data_json.get('secret') != SMS_WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    sms_text = data_json.get('sms_body', '')
    # Extract transaction ID
    txn_match = re.search(r'TXN[0-9]{10,}', sms_text)
    if not txn_match:
        return jsonify({"error": "No TXN ID"}), 400
    txn_id = txn_match.group()
    if txn_id in processed_txns:
        return jsonify({"status": "already_processed"}), 200
    processed_txns.add(txn_id)

    # Extract amount
    amount_match = re.search(r'[Rs₹]+\.?\s?(\d+)', sms_text, re.IGNORECASE)
    amount = int(amount_match.group(1)) if amount_match else 0

    # Match pending order
    matched = None
    for oid, order in pending_orders.items():
        if order['amount'] == amount:
            matched = oid
            break
    if not matched:
        return jsonify({"error": "No pending order with that amount"}), 404

    order = pending_orders[matched]
    key = pop_key(order['product'], order['duration'])
    if not key:
        key = generate_key(order['product'])

    save_user_key(order['user_id'], order['username'], PRODUCTS[order['product']]['name'], order['duration'], key)
    save_order({
        "username": order['username'],
        "product": PRODUCTS[order['product']]['name'],
        "duration": order['duration'],
        "amount": order['amount'],
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p"),
        "txn_id": txn_id
    })
    bot.send_message(order['chat_id'], f"✅ *Payment Verified!*\n\n🔑 Your Key: `{key}`\n\nThank you!", parse_mode="Markdown", reply_markup=main_menu())
    del pending_orders[matched]

    return jsonify({"status": "key_delivered", "order_id": matched}), 200

# ---------- Admin Panel Routes (minimal) ----------
@app.route('/')
def home():
    return jsonify({"status": "online", "auto_upi": True})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard')
def dashboard():
    total_keys = sum(get_stock(p,"day")+get_stock(p,"week")+get_stock(p,"month") for p in PRODUCTS)
    return jsonify({
        "total_keys": total_keys,
        "total_orders": len(data["orders"]),
        "total_users": len(data["users"]),
        "total_revenue": sum(o.get("amount",0) for o in data["orders"])
    })

@app.route('/api/keys/all')
def keys_all():
    return jsonify(data["keys"])

@app.route('/api/keys/<product>/<duration>')
def get_keys(product, duration):
    return jsonify({"keys": data["keys"].get(product, {}).get(duration, [])})

@app.route('/api/keys', methods=['POST'])
def add_keys():
    body = request.json
    add_keys_to_db(body['product'], body['duration'], body['keys'])
    return jsonify({"ok": True})

@app.route('/api/keys/generate', methods=['POST'])
def gen_keys():
    body = request.json
    p,d,c = body['product'], body['duration'], body['count']
    pre = PREFIX.get(p, "KEY")
    new = [f"{pre}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}" for _ in range(c)]
    add_keys_to_db(p, d, new)
    return jsonify({"ok": True})

@app.route('/api/keys/<product>/<duration>', methods=['DELETE'])
def clear_keys(product, duration):
    if product in data["keys"]:
        data["keys"][product][duration] = []
        save_data(data)
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
    return jsonify(data["orders"])

@app.route('/api/orders', methods=['DELETE'])
def del_orders():
    data["orders"] = []
    save_data(data)
    return jsonify({"ok": True})

@app.route('/api/users')
def get_users():
    return jsonify(data["users"])

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

if __name__ == "__main__":
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

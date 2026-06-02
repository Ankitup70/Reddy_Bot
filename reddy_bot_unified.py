#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT – FULLY IMPROVED (NO SETUP OPTION)
- Razorpay Auto Payment
- Stock Display + Low Stock Alerts
- Auto Key Generation on Low Stock
- Daily Sales Report
- Colorful Buttons
- Professional Invoice
- Duplicate Webhook Protection
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import string
import datetime
import threading
import time
import io
import qrcode
import os
import json
import razorpay
import hashlib
import hmac
import schedule
from flask import Flask, request, jsonify, send_from_directory

# ========== CONFIGURATION ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"
DATA_FILE = "bot_data.json"

# Razorpay Credentials (Replace with your own)
RAZORPAY_KEY_ID = "rzp_test_Swf7omML9UnAHQ"
RAZORPAY_KEY_SECRET = "70nCcG6l2fOXSijMSDB7UFuU"
RAZORPAY_WEBHOOK_SECRET = "MyRzpWebhookSecret@2024"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}
processed_payments = set()

# ========== DATA STORAGE ==========
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {},
        "orders": [],
        "keys": {p: {"day": [], "week": [], "month": []} for p in ["deadeye","vision","rage","winios","kingios"]},
        "processed_payments": []
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()
processed_payments = set(data.get("processed_payments", []))

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

# ========== DATABASE HELPERS ==========
def get_stock(product, duration):
    return len(data["keys"].get(product, {}).get(duration, []))

def pop_key(product, duration):
    pool = data["keys"].get(product, {}).get(duration, [])
    if pool:
        key = pool.pop(0)
        save_data(data)
        remaining = len(pool)
        if remaining <= 5:
            bot.send_message(ADMIN_ID, f"⚠️ *Low Stock Alert!*\n\n{PRODUCTS[product]['name']} - {duration}\nOnly {remaining} keys left.\nPlease add new keys.", parse_mode="Markdown")
            if remaining < 3:
                auto_refill_stock(product, duration)
        return key
    return None

def auto_refill_stock(product, duration, target=10):
    current = get_stock(product, duration)
    if current < target:
        needed = target - current
        prefix = PREFIX.get(product, "KEY")
        new_keys = []
        for _ in range(needed):
            k = f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"
            new_keys.append(k)
        if product not in data["keys"]:
            data["keys"][product] = {"day": [], "week": [], "month": []}
        data["keys"][product][duration].extend(new_keys)
        save_data(data)
        bot.send_message(ADMIN_ID, f"🤖 *Auto-Refill*\n{PRODUCTS[product]['name']} - {duration}\nAdded {needed} new keys.", parse_mode="Markdown")

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

def get_all_keys():
    return data["keys"]

def get_all_users():
    return data["users"]

def get_all_orders():
    return data["orders"]

def get_stats():
    total_orders = len(data["orders"])
    total_revenue = sum(o.get("amount", 0) for o in data["orders"])
    return {"total_orders": total_orders, "total_revenue": total_revenue}

# ========== RAZORPAY HELPERS ==========
def create_razorpay_order(amount, order_id, product, duration):
    try:
        razorpay_order = razorpay_client.order.create({
            "amount": int(amount * 100),
            "currency": "INR",
            "receipt": order_id,
            "notes": {
                "product": product,
                "duration": duration,
                "bot_order_id": order_id
            }
        })
        payment_link = f"https://rzp.io/l/{razorpay_order['id']}"
        return payment_link, razorpay_order['id']
    except Exception as e:
        print(f"Razorpay error: {e}")
        return None, None

def verify_webhook_signature(body, signature):
    try:
        expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except:
        return False

def deliver_key_from_razorpay(order_id, payment_details):
    if order_id not in pending_orders:
        return False
    o = pending_orders[order_id]
    if get_stock(o['product'], o['duration']) == 0:
        bot.send_message(ADMIN_ID, f"⚠️ Stock out for {PRODUCTS[o['product']]['name']} - {o['duration']}")
        return False
    key = pop_key(o['product'], o['duration'])
    if not key:
        return False
    save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
    save_order({
        "username": o['username'],
        "product": PRODUCTS[o['product']]['name'],
        "duration": o['duration'],
        "amount": o['amount'],
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p"),
        "payment_id": payment_details.get('payment_id', '')
    })
    # Invoice
    invoice = f"""🧾 *REDDY PREMIUM INVOICE*
━━━━━━━━━━━━━━━━━━━━━━
Order ID: `{order_id}`
Date: {datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")}
Product: {PRODUCTS[o['product']]['name']}
Duration: {o['duration']}
Amount: ₹{o['amount']}
Payment Status: ✅ Paid
━━━━━━━━━━━━━━━━━━━━━━
Thank you for choosing Reddy Premium!"""
    bot.send_message(o['chat_id'], invoice, parse_mode="Markdown")
    user_msg = f"""✅ *PAYMENT VERIFIED* ✅

🎉 Congratulations!

📦 {PRODUCTS[o['product']]['name']} ({o['duration']})
💰 ₹{o['amount']}

🔑 *Your License Key:*
`{key}`

📌 *How to use:*
1️⃣ Copy key
2️⃣ Open {PRODUCTS[o['product']]['name']}
3️⃣ Activate
4️⃣ Enjoy! 🚀

⚠️ Keep private, do not share.

👑 Thank you for choosing Reddy Premium!"""
    bot.send_message(o['chat_id'], user_msg, parse_mode="Markdown", reply_markup=main_menu())
    del pending_orders[order_id]
    return True

# ========== TELEGRAM KEYBOARDS (NO SETUP) ==========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Buy Now", callback_data="buy"),
        InlineKeyboardButton("🔑 My Keys", callback_data="mykeys"),
        InlineKeyboardButton("📦 Stock", callback_data="stock"),
        InlineKeyboardButton("💬 Support", callback_data="help"),
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
    
    day_btn = f"📅 1 Day - ₹{p['day']}" + (" 🔴" if day_stock == 0 else "")
    week_btn = f"📅 7 Days - ₹{p['week']}" + (" 🔴" if week_stock == 0 else "")
    month_btn = f"📅 30 Days - ₹{p['month']}" + (" 🔴" if month_stock == 0 else "")
    
    day_style = 'danger' if day_stock == 0 else 'primary'
    week_style = 'danger' if week_stock == 0 else 'primary'
    month_style = 'danger' if month_stock == 0 else 'primary'
    
    kb.add(InlineKeyboardButton(day_btn, callback_data=f"plan_{product}_day", style=day_style))
    kb.add(InlineKeyboardButton(week_btn, callback_data=f"plan_{product}_week", style=week_style))
    kb.add(InlineKeyboardButton(month_btn, callback_data=f"plan_{product}_month", style=month_style))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back", style='primary'))
    return kb

def pay_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}", style='danger'))
    return kb

def admin_kb(order_id, uid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ok_{order_id}_{uid}", style='success'))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"no_{order_id}_{uid}", style='danger'))
    return kb

# ========== BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    text = f"""✨👑 *REDDY PREMIUM* 👑✨

Hello {msg.from_user.first_name}!

💎 Trusted License Shop
⚡ Instant Delivery (Razorpay)
🛡️ 100% Genuine Keys

👇 Choose option
"""
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

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
        text = "📦 *Stock Available*\n\n"
        for key, p in PRODUCTS.items():
            d = get_stock(key, "day")
            w = get_stock(key, "week")
            m = get_stock(key, "month")
            if d + w + m > 0:
                text += f"{p['emoji']} *{p['name']}*\n   1D: {d} | 7D: {w} | 30D: {m}\n\n"
            else:
                text += f"{p['emoji']} *{p['name']}* - 🔴 Out of Stock\n\n"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data_cb == "mykeys":
        uid_str = str(uid)
        user_keys = data["users"].get(uid_str, {}).get("keys", [])
        if not user_keys:
            text = "🔑 *My Keys*\n\nYou have no keys yet.\nUse Buy option."
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = "🔑 *Your Keys*\n\n"
            for k in user_keys[-5:][::-1]:
                text += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data_cb == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
        text = "💬 *Support*\n\n📞 @ReddyHack\n24/7 Available"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif data_cb.startswith("prod_"):
        product = data_cb.split("_")[1]
        p = PRODUCTS[product]
        text = f"{p['emoji']} *{p['name']}*\n\n💰 *Prices*\n"
        text += f"🟢 1 Day - ₹{PRICES[product]['day']}\n"
        text += f"🟡 7 Days - ₹{PRICES[product]['week']}\n"
        text += f"🔴 30 Days - ₹{PRICES[product]['month']}\n\n"
        text += "✅ Choose your plan 👇"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    
    elif data_cb.startswith("plan_"):
        _, product, duration = data_cb.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Sold out! Choose another.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        
        payment_link, razorpay_order_id = create_razorpay_order(amount, order_id, product, duration)
        if not payment_link:
            bot.answer_callback_query(call.id, "❌ Payment error! Try later.", show_alert=True)
            return
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid,
            "razorpay_order_id": razorpay_order_id
        }
        
        caption = f"""💳 *RAZORPAY PAYMENT*

🆔 Order: `{order_id}`
📦 {PRODUCTS[product]['name']}
⏱️ {duration}
💰 ₹{amount}

👉 [PAY NOW]({payment_link})

✅ After payment, key will be sent automatically.
⏳ Complete within 15 minutes."""
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💳 PAY NOW", url=payment_link))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}", style='danger'))
        
        bot.delete_message(cid, call.message.id)
        bot.send_message(cid, caption, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
        
        threading.Timer(900, lambda: expire(order_id, cid)).start()
    
    elif data_cb.startswith("cancel_"):
        order_id = data_cb.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_text("❌ *Order Cancelled*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        bot.send_message(cid, "🔄 Start again 👇", reply_markup=main_menu())

def expire(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order expired*\nPlease start fresh.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ========== RAZORPAY WEBHOOK ==========
@app.route('/razorpay_webhook', methods=['POST'])
def razorpay_webhook():
    signature = request.headers.get('X-Razorpay-Signature')
    if not signature or not verify_webhook_signature(request.get_data(as_text=True), signature):
        return jsonify({"error": "Invalid signature"}), 400
    webhook_data = request.json
    if webhook_data.get('event') == 'payment.captured':
        payment = webhook_data.get('payload', {}).get('payment', {}).get('entity', {})
        rzp_order_id = payment.get('order_id')
        # Check duplicate
        if rzp_order_id in processed_payments:
            return jsonify({"status": "already_processed"}), 200
        # Find internal order
        internal_id = None
        for oid, od in pending_orders.items():
            if od.get('razorpay_order_id') == rzp_order_id:
                internal_id = oid
                break
        if internal_id:
            deliver_key_from_razorpay(internal_id, payment)
            processed_payments.add(rzp_order_id)
            data["processed_payments"] = list(processed_payments)
            save_data(data)
    return jsonify({"status": "ok"}), 200

# ========== DAILY REPORT SCHEDULER ==========
def send_daily_report():
    today_str = datetime.datetime.now().strftime("%d %b %Y")
    today_orders = [o for o in data["orders"] if o.get("date", "").startswith(today_str)]
    total_sales = sum(o.get("amount", 0) for o in today_orders)
    msg = f"📊 *Daily Sales Report* – {today_str}\n\nOrders: {len(today_orders)}\nRevenue: ₹{total_sales}\n\n✅ Bot running smoothly."
    bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")

def run_scheduler():
    schedule.every().day.at("23:59").do(send_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler thread
threading.Thread(target=run_scheduler, daemon=True).start()

# ========== FLASK API FOR ADMIN PANEL ==========
@app.route('/')
def home():
    return jsonify({"status": "online", "payment": "razorpay"})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard')
def dashboard():
    stats = get_stats()
    total_keys = sum(get_stock(p, "day") + get_stock(p, "week") + get_stock(p, "month") for p in PRODUCTS)
    return jsonify({
        "total_keys": total_keys,
        "total_orders": stats["total_orders"],
        "total_users": len(data["users"]),
        "total_revenue": stats["total_revenue"]
    })

@app.route('/api/keys/all')
def keys_all():
    return jsonify(get_all_keys())

@app.route('/api/keys/<product>/<duration>')
def get_keys(product, duration):
    keys = data["keys"].get(product, {}).get(duration, [])
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
    def g():
        return f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"
    new_keys = [g() for _ in range(count)]
    add_keys_to_db(product, duration, new_keys)
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
    return jsonify(get_all_orders())

@app.route('/api/orders', methods=['DELETE'])
def del_orders():
    data["orders"] = []
    save_data(data)
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

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 REDDY BOT - SETUP REMOVED")
    print("=" * 50)
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

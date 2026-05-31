#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - SIMPLE & PROFESSIONAL
Clean, Trustworthy, Customer Friendly
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
from flask import Flask, request, jsonify, send_from_directory

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}

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

# Database
db = {
    "users": {},
    "orders": [],
    "keys": {p: {"day": [], "week": [], "month": []} for p in PRODUCTS},
}

# ============================================================
# HELPERS
# ============================================================

def get_stock(product, duration):
    try:
        return len(db["keys"].get(product, {}).get(duration, []))
    except:
        return 0

def pop_key(product, duration):
    pool = db["keys"].get(product, {}).get(duration, [])
    if pool:
        return pool.pop(0)
    return None

def save_user_key(user_id, username, product, duration, key):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {"username": username, "keys": []}
    db["users"][uid]["keys"].append({
        "product": product, "duration": duration, "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    })

def make_qr(amount, order_id):
    upi = f"upi://pay?pa=q542401897@ybl&pn=Reddy+Premium&am={amount}&tn={order_id}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ============================================================
# KEYBOARDS - SIMPLE & CLEAN
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Buy", callback_data="buy"),
        InlineKeyboardButton("🔑 My Keys", callback_data="mykeys"),
        InlineKeyboardButton("📦 Stock", callback_data="stock"),
        InlineKeyboardButton("💬 Help", callback_data="help"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
    return kb

def plans_kb(product):
    kb = InlineKeyboardMarkup(row_width=1)
    prices = PRICES[product]
    
    day_stock = get_stock(product, "day")
    week_stock = get_stock(product, "week")
    month_stock = get_stock(product, "month")
    
    day_btn = f"📅 1 Day - ₹{prices['day']}"
    week_btn = f"📅 7 Days - ₹{prices['week']}"
    month_btn = f"📅 30 Days - ₹{prices['month']}"
    
    if day_stock == 0:
        day_btn = f"📅 1 Day - ₹{prices['day']} ❌"
    if week_stock == 0:
        week_btn = f"📅 7 Days - ₹{prices['week']} ❌"
    if month_stock == 0:
        month_btn = f"📅 30 Days - ₹{prices['month']} ❌"
    
    kb.add(InlineKeyboardButton(day_btn, callback_data=f"plan_{product}_day"))
    kb.add(InlineKeyboardButton(week_btn, callback_data=f"plan_{product}_week"))
    kb.add(InlineKeyboardButton(month_btn, callback_data=f"plan_{product}_month"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
    return kb

def pay_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Paid", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, uid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ok_{order_id}_{uid}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"no_{order_id}_{uid}"))
    return kb

# ============================================================
# MESSAGES - SIMPLE & WELCOMING
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    text = f"""
👋 Hello {msg.from_user.first_name}!

Welcome to *Reddy Premium*

💎 Trusted License Shop
⚡ Instant Delivery
🛡️ 100% Genuine Keys

👇 Tap below to start
"""
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    # Back to main menu
    if data == "back":
        bot.edit_message_text("👇 *Choose an option*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    # Main menu options
    elif data == "buy":
        bot.edit_message_text("🛒 *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "mykeys":
        uid_str = str(uid)
        keys = db["users"].get(uid_str, {}).get("keys", [])
        if not keys:
            text = "🔑 *My Keys*\n\nYou don't have any keys yet.\n\nUse Buy option to purchase."
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = "🔑 *Your Keys*\n\n"
            for k in keys[-5:]:
                text += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "stock":
        text = "📦 *Stock Available*\n\n"
        for key, p in PRODUCTS.items():
            day = get_stock(key, "day")
            week = get_stock(key, "week")
            month = get_stock(key, "month")
            total = day + week + month
            if total > 0:
                text += f"{p['emoji']} {p['name']}\n   1D:{day} | 7D:{week} | 30D:{month}\n\n"
            else:
                text += f"{p['emoji']} {p['name']} - Out of Stock\n\n"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
        text = "💬 *Need Help?\n\nContact our support team\n\n@ReddyHack"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    # Product selected
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        text = f"{p['emoji']} *{p['name']}*\n\nChoose your plan:"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    
    # Plan selected
    elif data.startswith("plan_"):
        parts = data.split("_")
        product = parts[1]
        duration = parts[2]
        
        stock = get_stock(product, duration)
        if stock == 0:
            bot.answer_callback_query(call.id, "❌ Sold out! Please choose another plan.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_qr(amount, order_id)
        
        caption = f"""
🛒 *Order #{order_id}*

📦 {PRODUCTS[product]['name']}
⏱️ {duration}
💰 ₹{amount}

━━━━━━━━━━━━━━━━
📲 *UPI:* `q542401897@ybl`

✅ Pay & tap "Paid"
🔑 Key will be sent
━━━━━━━━━━━━━━━━
"""
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=pay_kb(order_id))
        
        threading.Timer(900, lambda: expire(order_id, cid)).start()
    
    # User says paid
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Admin notified!")
        
        msg = f"""
🔔 *Payment Received*

👤 @{uname}
📦 {PRODUCTS[o['product']]['name']}
⏱️ {o['duration']}
💰 ₹{o['amount']}
🆔 {order_id}

✅ Verify & Send Key
"""
        bot.send_message(ADMIN_ID, msg, parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    # Admin approve
    elif data.startswith("ok_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!")
            return
        
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired!")
            return
        
        o = pending_orders[order_id]
        
        if get_stock(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "No stock! Add keys first.")
            return
        
        key = pop_key(o['product'], o['duration'])
        if not key:
            bot.answer_callback_query(call.id, "Error! No key.")
            return
        
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        
        db["orders"].append({
            "username": o['username'],
            "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'],
            "amount": o['amount'],
            "key": key,
            "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
        })
        
        user_msg = f"""
✅ *Payment Verified!*

📦 {PRODUCTS[o['product']]['name']}
⏱️ {o['duration']}
💰 ₹{o['amount']}

🔑 *Your Key:*
`{key}`

💡 Copy and activate!

Thank you! 👑
"""
        bot.send_message(user_cid, user_msg, parse_mode="Markdown", reply_markup=main_menu())
        
        bot.answer_callback_query(call.id, "✅ Key sent!")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    # Admin reject
    elif data.startswith("no_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!")
            return
        
        bot.send_message(user_cid, "❌ *Payment not verified*\n\nPlease try again or contact support.", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    # Cancel order
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ Cancelled", reply_markup=None)
        bot.send_message(cid, "Start over from main menu 👇", reply_markup=main_menu())

def expire(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order expired*\n\nPlease start again.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API
# ============================================================

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": "@ReddyBot"})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard')
def dashboard():
    total_keys = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    return jsonify({
        "total_keys": total_keys,
        "total_orders": len(db["orders"]),
        "total_users": len(db["users"]),
        "total_revenue": sum(o.get("amount",0) for o in db["orders"])
    })

@app.route('/api/keys/all')
def keys_all():
    return jsonify(db["keys"])

@app.route('/api/keys/<p>/<d>')
def get_keys(p, d):
    return jsonify({"keys": db["keys"].get(p, {}).get(d, [])})

@app.route('/api/keys', methods=['POST'])
def add_keys():
    data = request.json
    p, d, ks = data['product'], data['duration'], data['keys']
    if p not in db["keys"]:
        db["keys"][p] = {"day": [], "week": [], "month": []}
    db["keys"][p][d].extend(ks)
    return jsonify({"ok": True})

@app.route('/api/keys/generate', methods=['POST'])
def gen_keys():
    data = request.json
    p, d, c = data['product'], data['duration'], data['count']
    pre = PREFIX.get(p, "KEY")
    def g():
        return f"{pre}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"
    new = [g() for _ in range(c)]
    if p not in db["keys"]:
        db["keys"][p] = {"day": [], "week": [], "month": []}
    db["keys"][p][d].extend(new)
    return jsonify({"ok": True})

@app.route('/api/keys/<p>/<d>', methods=['DELETE'])
def clear_keys(p, d):
    if p in db["keys"]:
        db["keys"][p][d] = []
    return jsonify({"ok": True})

@app.route('/api/prices')
def get_prices():
    return jsonify(PRICES)

@app.route('/api/prices', methods=['POST'])
def set_prices():
    data = request.json
    PRICES[data['product']] = data['prices']
    return jsonify({"ok": True})

@app.route('/api/orders')
def get_orders():
    return jsonify(db["orders"])

@app.route('/api/orders', methods=['DELETE'])
def del_orders():
    db["orders"] = []
    return jsonify({"ok": True})

@app.route('/api/users')
def get_users():
    return jsonify(db["users"])

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
    print("=" * 40)
    print("🤖 REDDY BOT STARTING...")
    print("=" * 40)
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

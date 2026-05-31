#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - COMPLETE WITH ADMIN PANEL
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
    "deadeye": {"name": "Deadeye", "emoji": "🎯", "prefix": "DEAD"},
    "vision": {"name": "Vision", "emoji": "👁️", "prefix": "VIS"},
    "rage": {"name": "Rage", "emoji": "⚡", "prefix": "RAGE"},
    "winios": {"name": "Winios", "emoji": "💻", "prefix": "WIN"},
    "kingios": {"name": "Kingios", "emoji": "👑", "prefix": "KING"},
}

PRICES = {
    "deadeye": {"day": 149, "week": 699, "month": 1299},
    "vision": {"day": 199, "week": 699, "month": 2200},
    "rage": {"day": 149, "week": 699, "month": 1299},
    "winios": {"day": 149, "week": 599, "month": 999},
    "kingios": {"day": 199, "week": 699, "month": 2200},
}

# Database
db = {
    "users": {},
    "orders": [],
    "keys": {p: {"day": [], "week": [], "month": []} for p in PRODUCTS},
}

def save_user_key(user_id, username, product, duration, key):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {"username": username, "keys": []}
    db["users"][uid]["keys"].append({
        "product": product, "duration": duration, "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    })

def make_upi_qr(amount, order_id):
    upi = f"upi://pay?pa=q542401897@ybl&pn=Reddy+Premium&am={amount}&tn={order_id}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi)
    qr.make()
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Purchase", callback_data="purchase"),
        InlineKeyboardButton("🔑 My Keys", callback_data="my_keys"),
        InlineKeyboardButton("🆘 Support", callback_data="support"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb

def duration_kb(product):
    p = PRICES[product]
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton(f"🟢 Day ₹{p['day']}", callback_data=f"dur_{product}_day"),
        InlineKeyboardButton(f"🟡 Week ₹{p['week']}", callback_data=f"dur_{product}_week"),
        InlineKeyboardButton(f"🔴 Month ₹{p['month']}", callback_data=f"dur_{product}_month"),
    )
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="purchase"))
    return kb

def payment_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{order_id}_{user_id}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}_{user_id}"))
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, 
        "👑 *REDDY PREMIUM SHOP* 👑\n\n"
        "✨ Premium License Keys\n"
        "⚡ Instant Delivery\n"
        "🛡️ 100% Trusted\n\n"
        "👇 *Choose an option:*",
        parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "main_menu":
        bot.edit_message_text("👑 *Main Menu*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "purchase":
        bot.edit_message_text("🛒 *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        bot.edit_message_text(f"📦 *{PRODUCTS[product]['name']}* - Select Duration", cid, call.message.id, parse_mode="Markdown", reply_markup=duration_kb(product))
    
    elif data.startswith("dur_"):
        _, product, duration = data.split("_")
        amount = PRICES[product][duration]
        order_id = f"ORD{int(time.time())}{random.randint(100,999)}"
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_upi_qr(amount, order_id)
        caption = f"🛒 *Order ID:* `{order_id}`\n\n📦 *Product:* {PRODUCTS[product]['name']}\n⏱️ *Duration:* {duration}\n💰 *Amount:* ₹{amount}\n\n📲 *UPI ID:* `q542401897@ybl`\n\n*Scan QR or Pay & Click 'I have paid'*"
        
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=payment_kb(order_id))
        
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Admin notified! Will deliver soon.")
        
        bot.send_message(ADMIN_ID, f"🔔 *PAYMENT CLAIM*\n\n👤 @{uname}\n📦 {PRODUCTS[o['product']]['name']}\n⏱️ {o['duration']}\n💰 ₹{o['amount']}\n🆔 `{order_id}`", parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("approve_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Only admin!")
            return
        
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired!")
            return
        
        o = pending_orders[order_id]
        prefix = PRODUCTS[o['product']]['prefix']
        key = f"{prefix}-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))}"
        
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        
        db["orders"].append({
            "username": o['username'],
            "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'],
            "amount": o['amount'],
            "key": key,
            "date": datetime.datetime.now().strftime("%d %b %Y")
        })
        
        bot.send_message(user_cid, f"✅ *KEY DELIVERED!*\n\n📦 {PRODUCTS[o['product']]['name']}\n🔑 `{key}`\n\nThank you for choosing Reddy Premium! 👑", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "✅ Approved! Key sent.")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("reject_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Only admin!")
            return
        
        bot.send_message(user_cid, "❌ *Payment not verified.* Please try again.", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ Order Cancelled", reply_markup=None)
    
    elif data == "my_keys":
        uid = str(call.from_user.id)
        keys = db["users"].get(uid, {}).get("keys", [])
        if not keys:
            bot.edit_message_text("🔑 *No keys purchased yet*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            msg = "🔑 *Your Keys*\n\n"
            for k in keys[-5:]:
                msg += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "support":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact Support", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        bot.edit_message_text("🆘 *Support*\n\nContact: @ReddyHack", cid, call.message.id, parse_mode="Markdown", reply_markup=kb)

def expire_order(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order Expired!* Please purchase again.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# ADMIN PANEL API ROUTES
# ============================================================

@app.route('/')
def home():
    return jsonify({"bot": "@ReddyBot", "status": "Bot is running!"})

@app.route('/admin')
def admin_panel():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    total_keys = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    total_revenue = sum(o.get("amount", 0) for o in db["orders"])
    return jsonify({
        "total_keys": total_keys,
        "total_orders": len(db["orders"]),
        "total_users": len(db["users"]),
        "total_revenue": total_revenue
    })

@app.route('/api/keys/all', methods=['GET'])
def api_keys_all():
    return jsonify(db["keys"])

@app.route('/api/keys/<product>/<duration>', methods=['GET'])
def api_get_keys(product, duration):
    return jsonify({"keys": db["keys"].get(product, {}).get(duration, [])})

@app.route('/api/keys', methods=['POST'])
def api_add_keys():
    data = request.json
    product = data.get('product')
    duration = data.get('duration')
    keys = data.get('keys', [])
    if product not in db["keys"]:
        db["keys"][product] = {"day": [], "week": [], "month": []}
    db["keys"][product][duration].extend(keys)
    return jsonify({"success": True, "added": len(keys)})

@app.route('/api/keys/generate', methods=['POST'])
def api_generate_keys():
    data = request.json
    product = data.get('product')
    duration = data.get('duration')
    count = data.get('count', 10)
    prefix = data.get('prefix', 'KEY')
    def gen():
        parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)]
        return f"{prefix}-{'-'.join(parts)}"
    new_keys = [gen() for _ in range(count)]
    if product not in db["keys"]:
        db["keys"][product] = {"day": [], "week": [], "month": []}
    db["keys"][product][duration].extend(new_keys)
    return jsonify({"success": True, "keys": new_keys})

@app.route('/api/keys/<product>/<duration>', methods=['DELETE'])
def api_clear_keys(product, duration):
    if product in db["keys"]:
        db["keys"][product][duration] = []
    return jsonify({"success": True})

@app.route('/api/prices', methods=['GET'])
def api_get_prices():
    return jsonify(PRICES)

@app.route('/api/prices', methods=['POST'])
def api_update_prices():
    data = request.json
    product = data.get('product')
    prices = data.get('prices')
    PRICES[product] = prices
    return jsonify({"success": True})

@app.route('/api/orders', methods=['GET'])
def api_get_orders():
    return jsonify(db["orders"])

@app.route('/api/orders', methods=['DELETE'])
def api_clear_orders():
    db["orders"] = []
    return jsonify({"success": True})

@app.route('/api/users', methods=['GET'])
def api_get_users():
    return jsonify(db["users"])

@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.json
    if data.get('password') == "reddy2024":
        return jsonify({"token": "reddy2024", "success": True})
    return jsonify({"error": "Wrong password"}), 401

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 REDDY PREMIUM BOT WITH ADMIN PANEL")
    print("=" * 50)
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ Admin Panel: /admin")
    print("=" * 50)
    
    # Remove webhook and use polling
    bot.remove_webhook()
    
    # Start bot in background thread
    def run_bot():
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=8080)

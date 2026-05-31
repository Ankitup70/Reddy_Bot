#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - CLEAN & ATTRACTIVE EDITION
Simple, Professional, No Overload
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
    "deadeye": {"name": "🎯 Deadeye", "prefix": "DEAD", "emoji": "🎯"},
    "vision": {"name": "👁️ Vision", "prefix": "VIS", "emoji": "👁️"},
    "rage": {"name": "⚡ Rage", "prefix": "RAGE", "emoji": "⚡"},
    "winios": {"name": "💻 WinIOS", "prefix": "WIN", "emoji": "💻"},
    "kingios": {"name": "👑 KingIOS", "prefix": "KING", "emoji": "👑"},
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

# ============================================================
# HELPERS
# ============================================================

def get_stock_count(product, duration):
    try:
        return len(db["keys"].get(product, {}).get(duration, []))
    except:
        return 0

def get_stock_emoji(count):
    if count == 0:
        return "🔴"
    elif count < 5:
        return "🟡"
    else:
        return "🟢"

def pop_key(product, duration):
    pool = db["keys"].get(product, {}).get(duration, [])
    if pool:
        key = pool.pop(0)
        return key
    return None

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
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ============================================================
# KEYBOARDS - CLEAN & SIMPLE
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Buy License", callback_data="purchase"),
        InlineKeyboardButton("🔑 My Keys", callback_data="my_keys"),
        InlineKeyboardButton("📦 Stock", callback_data="stock_status"),
        InlineKeyboardButton("💬 Support", callback_data="support"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        total = get_stock_count(key, "day") + get_stock_count(key, "week") + get_stock_count(key, "month")
        emoji = "🔴" if total == 0 else "🟢" if total > 10 else "🟡"
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} {emoji}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("◀️ Main Menu", callback_data="main_menu"))
    return kb

def duration_kb(product):
    kb = InlineKeyboardMarkup(row_width=1)
    prices = PRICES[product]
    
    day_stock = get_stock_count(product, "day")
    week_stock = get_stock_count(product, "week")
    month_stock = get_stock_count(product, "month")
    
    day_emoji = "🔴" if day_stock == 0 else "🟢" if day_stock > 5 else "🟡"
    week_emoji = "🔴" if week_stock == 0 else "🟢" if week_stock > 5 else "🟡"
    month_emoji = "🔴" if month_stock == 0 else "🟢" if month_stock > 5 else "🟡"
    
    day_text = f"{day_emoji} 24 Hours - ₹{prices['day']}"
    week_text = f"{week_emoji} 7 Days - ₹{prices['week']}"
    month_text = f"{month_emoji} 30 Days - ₹{prices['month']}"
    
    if day_stock == 0:
        day_text = f"🔴 24 Hours - ₹{prices['day']} (Sold Out)"
    if week_stock == 0:
        week_text = f"🔴 7 Days - ₹{prices['week']} (Sold Out)"
    if month_stock == 0:
        month_text = f"🔴 30 Days - ₹{prices['month']} (Sold Out)"
    
    kb.add(InlineKeyboardButton(day_text, callback_data=f"dur_{product}_day"))
    kb.add(InlineKeyboardButton(week_text, callback_data=f"dur_{product}_week"))
    kb.add(InlineKeyboardButton(month_text, callback_data=f"dur_{product}_month"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="purchase"))
    
    return kb

def payment_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve & Send Key", callback_data=f"approve_{order_id}_{user_id}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}_{user_id}"))
    return kb

def back_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Main Menu", callback_data="main_menu"))
    return kb

# ============================================================
# MESSAGES - CLEAN & ATTRACTIVE
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    text = f"""
✨ *Welcome to Reddy Premium* ✨

━━━━━━━━━━━━━━━━━━━━━━
💎 *Premium License Shop*
⚡ *Instant Delivery*
🛡️ *100% Trusted*
━━━━━━━━━━━━━━━━━━━━━━

👋 Hello @{msg.from_user.username or msg.from_user.first_name}!

👇 *Choose an option below*
"""
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "main_menu":
        bot.edit_message_text("✨ *Main Menu* ✨\n\n👇 Choose an option:", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "purchase":
        text = "🛒 *Select a product*\n\nChoose from our premium collection:"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "stock_status":
        text = "📦 *Current Stock Status*\n\n"
        for key, p in PRODUCTS.items():
            day = get_stock_count(key, "day")
            week = get_stock_count(key, "week")
            month = get_stock_count(key, "month")
            total = day + week + month
            if total > 0:
                text += f"{p['emoji']} *{p['name']}*\n"
                text += f"  24H: {day} | 7D: {week} | 30D: {month}\n\n"
            else:
                text += f"{p['emoji']} *{p['name']}* - 🔴 Out of Stock\n\n"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=back_kb())
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        text = f"{p['emoji']} *{p['name']}*\n\n💰 *Prices*\n━━━━━━━━━━━━━━━━\n"
        text += f"🟢 24 Hours - ₹{PRICES[product]['day']}\n"
        text += f"🟡 7 Days - ₹{PRICES[product]['week']}\n"
        text += f"🔴 30 Days - ₹{PRICES[product]['month']}\n"
        text += "━━━━━━━━━━━━━━━━\n✅ *Instant delivery after payment*"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=duration_kb(product))
    
    elif data.startswith("dur_"):
        _, product, duration = data.split("_")
        
        if get_stock_count(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Sold out! Please choose another plan.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"RDY{int(time.time())}{random.randint(100,999)}"
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_upi_qr(amount, order_id)
        
        caption = f"""
🛒 *Order #`{order_id}`*

📦 Product: {PRODUCTS[product]['name']}
⏱️ Duration: {duration}
💰 Amount: ₹{amount}

━━━━━━━━━━━━━━━━
📲 *UPI Payment*
`q542401897@ybl`

💡 *After payment, tap "I have paid"*
🔑 *Key will be delivered instantly*
━━━━━━━━━━━━━━━━
"""
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=payment_kb(order_id))
        
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "❌ Order expired!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Admin notified! Key coming soon.")
        
        admin_text = f"""
🔔 *New Payment Claim*

👤 User: @{uname}
🆔 ID: `{uid}`
📦 Product: {PRODUCTS[o['product']]['name']}
⏱️ Duration: {o['duration']}
💰 Amount: ₹{o['amount']}
🆔 Order: `{order_id}`

⚠️ *Verify payment in UPI app*
✅ *Then approve to send key*
"""
        bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("approve_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin only!")
            return
        
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "❌ Order expired!")
            return
        
        o = pending_orders[order_id]
        
        if get_stock_count(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "❌ No stock! Add keys first.")
            return
        
        key = pop_key(o['product'], o['duration'])
        
        if not key:
            bot.answer_callback_query(call.id, "❌ Failed! No key available.")
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
        
        user_text = f"""
✅ *Payment Verified!*

━━━━━━━━━━━━━━━━
📦 *Product:* {PRODUCTS[o['product']]['name']}
⏱️ *Duration:* {o['duration']}
💰 *Amount:* ₹{o['amount']}
━━━━━━━━━━━━━━━━

🔑 *Your License Key:*
`{key}`

💡 *How to use:*
1. Copy this key
2. Open {PRODUCTS[o['product']]['name']}
3. Paste and Activate
4. Enjoy! 🎉

━━━━━━━━━━━━━━━━
👑 *Thank you for choosing Reddy Premium!*
"""
        bot.send_message(user_cid, user_text, parse_mode="Markdown", reply_markup=main_menu())
        
        remaining = get_stock_count(o['product'], o['duration'])
        bot.send_message(ADMIN_ID, f"✅ Order completed! {remaining} keys left in stock")
        
        bot.answer_callback_query(call.id, "✅ Key delivered!")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("reject_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin only!")
            return
        
        bot.send_message(user_cid, "❌ *Payment not verified*\n\nPlease contact support for assistance.", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ *Order Cancelled*", reply_markup=None)
        bot.send_message(cid, "🔄 *Start over from main menu*", parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "my_keys":
        uid_str = str(call.from_user.id)
        keys_list = db["users"].get(uid_str, {}).get("keys", [])
        if not keys_list:
            text = "🔑 *My Keys*\n\nYou haven't purchased any keys yet.\n\n🛒 *Buy now from the main menu!*"
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = "🔑 *Your Purchased Keys*\n\n"
            for k in keys_list[-5:]:
                text += f"📦 *{k['product']}* ({k['duration']})\n"
                text += f"🔑 `{k['key']}`\n"
                text += f"📅 {k['date']}\n━━━━━━━━━━━━━━━━\n"
            text += "\n⚠️ *Keep your keys private!*"
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "support":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact Support", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("◀️ Main Menu", callback_data="main_menu"))
        text = "💬 *Support*\n\nFor any issues or queries, contact our support team.\n\n📞 @ReddyHack"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)

def expire_order(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order Expired*\n\nTime limit exceeded. Please start a new purchase.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API ROUTES
# ============================================================

@app.route('/')
def home():
    total_keys = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    return jsonify({"bot": "@ReddyBot", "status": "Online", "keys": total_keys})

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
    keys_list = data.get('keys', [])
    if product not in db["keys"]:
        db["keys"][product] = {"day": [], "week": [], "month": []}
    db["keys"][product][duration].extend(keys_list)
    return jsonify({"success": True})

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
    return jsonify({"success": True})

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
    print("👑 REDDY PREMIUM BOT - CLEAN EDITION")
    print("=" * 50)
    print("✅ Bot starting...")
    
    bot.remove_webhook()
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(url=f"{render_url}/webhook")
    
    app.run(host='0.0.0.0', port=8080)

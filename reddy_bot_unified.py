#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - With Stock Display Feature
Customer sees stock count, keys hidden until purchase
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

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_stock_count(product, duration):
    """Returns number of keys available in stock"""
    try:
        return len(db["keys"].get(product, {}).get(duration, []))
    except:
        return 0

def get_stock_status(product, duration):
    """Returns emoji based on stock availability"""
    count = get_stock_count(product, duration)
    if count == 0:
        return "❌ OUT OF STOCK"
    elif count < 5:
        return f"⚠️ Only {count} left!"
    elif count < 20:
        return f"✅ {count} in stock"
    else:
        return f"🔥 {count} in stock"

def can_deliver(product, duration):
    """Check if key is available for instant delivery"""
    return get_stock_count(product, duration) > 0

def pop_key(product, duration):
    """Get and remove a key from stock"""
    pool = db["keys"].get(product, {}).get(duration, [])
    if pool:
        key = pool.pop(0)
        # Sync with API
        try:
            requests.post('/api/keys', json={'product': product, 'duration': duration, 'keys': pool})
        except:
            pass
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
    # Sync with API
    try:
        requests.post('/api/users/key', json={'user_id': user_id, 'username': username, 'product': product, 'duration': duration, 'key': key})
    except:
        pass

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

# ============================================================
# KEYBOARDS WITH STOCK DISPLAY
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Purchase", callback_data="purchase"),
        InlineKeyboardButton("🔑 My Keys", callback_data="my_keys"),
        InlineKeyboardButton("📊 Stock Status", callback_data="stock_status"),
        InlineKeyboardButton("🆘 Support", callback_data="support"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        # Calculate total stock for this product
        total_stock = get_stock_count(key, "day") + get_stock_count(key, "week") + get_stock_count(key, "month")
        stock_emoji = "🔥" if total_stock > 50 else "✅" if total_stock > 10 else "⚠️" if total_stock > 0 else "❌"
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} {stock_emoji} ({total_stock})", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb

def duration_kb(product):
    p = PRODUCTS[product]
    prices = PRICES[product]
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Day Button with Stock Info
    day_stock = get_stock_count(product, "day")
    day_status = get_stock_status(product, "day")
    day_text = f"🟢 Day - ₹{prices['day']} ({day_status})"
    day_callback = f"dur_{product}_day"
    
    # Week Button with Stock Info
    week_stock = get_stock_count(product, "week")
    week_status = get_stock_status(product, "week")
    week_text = f"🟡 Week - ₹{prices['week']} ({week_status})"
    week_callback = f"dur_{product}_week"
    
    # Month Button with Stock Info
    month_stock = get_stock_count(product, "month")
    month_status = get_stock_status(product, "month")
    month_text = f"🔴 Month - ₹{prices['month']} ({month_status})"
    month_callback = f"dur_{product}_month"
    
    # Disable buttons if out of stock
    if day_stock == 0:
        day_text = f"🟢 Day - ₹{prices['day']} ❌ OUT OF STOCK"
    if week_stock == 0:
        week_text = f"🟡 Week - ₹{prices['week']} ❌ OUT OF STOCK"
    if month_stock == 0:
        month_text = f"🔴 Month - ₹{prices['month']} ❌ OUT OF STOCK"
    
    kb.add(InlineKeyboardButton(day_text, callback_data=day_callback))
    kb.add(InlineKeyboardButton(week_text, callback_data=week_callback))
    kb.add(InlineKeyboardButton(month_text, callback_data=month_callback))
    kb.add(InlineKeyboardButton("🔙 Back", callback_data="purchase"))
    
    return kb

def payment_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve & Deliver", callback_data=f"approve_{order_id}_{user_id}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"reject_{order_id}_{user_id}"))
    return kb

# ============================================================
# BOT COMMANDS & HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, 
        "👑 *REDDY PREMIUM SHOP* 👑\n\n"
        "✨ *Premium License Keys*\n"
        "⚡ *Instant Delivery*\n"
        "🛡️ *100% Trusted*\n\n"
        "📊 *Stock Status:*\n"
        "🟢 Available | ⚠️ Low Stock | ❌ Out of Stock\n\n"
        "👇 *Choose an option below:*",
        parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "main_menu":
        bot.edit_message_text("👑 *Main Menu*\n\nChoose an option below:", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "purchase":
        bot.edit_message_text("🛒 *Select Product*\n\nChoose from our premium collection:", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "stock_status":
        # Show full stock status
        stock_msg = "📊 *COMPLETE STOCK STATUS*\n\n"
        for key, p in PRODUCTS.items():
            day = get_stock_count(key, "day")
            week = get_stock_count(key, "week")
            month = get_stock_count(key, "month")
            total = day + week + month
            status = "🟢" if total > 0 else "🔴"
            stock_msg += f"{p['emoji']} *{p['name']}* {status}\n"
            stock_msg += f"   🟢 Day: {day} keys\n"
            stock_msg += f"   🟡 Week: {week} keys\n"
            stock_msg += f"   🔴 Month: {month} keys\n\n"
        stock_msg += f"\n{'-'*30}\n✅ *Instant Delivery Guaranteed!*"
        bot.edit_message_text(stock_msg, cid, call.message.id, parse_mode="Markdown", reply_markup=back_menu_kb())
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        stock_msg = f"{p['emoji']} *{p['name']} - SELECT DURATION*\n\n"
        stock_msg += f"🟢 Day: {get_stock_count(product, 'day')} keys available\n"
        stock_msg += f"🟡 Week: {get_stock_count(product, 'week')} keys available\n"
        stock_msg += f"🔴 Month: {get_stock_count(product, 'month')} keys available\n\n"
        stock_msg += f"✅ *Pay and get key INSTANTLY!*"
        bot.edit_message_text(stock_msg, cid, call.message.id, parse_mode="Markdown", reply_markup=duration_kb(product))
    
    elif data.startswith("dur_"):
        _, product, duration = data.split("_")
        
        # Check stock before proceeding
        if get_stock_count(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Sorry! This plan is OUT OF STOCK. Please choose another duration.")
            return
        
        amount = PRICES[product][duration]
        order_id = f"ORD{int(time.time())}{random.randint(100,999)}"
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_upi_qr(amount, order_id)
        caption = f"🛒 *Order ID:* `{order_id}`\n\n"
        caption += f"📦 *Product:* {PRODUCTS[product]['name']}\n"
        caption += f"⏱️ *Duration:* {duration.capitalize()}\n"
        caption += f"💰 *Amount:* ₹{amount}\n"
        caption += f"✅ *Stock Available:* {get_stock_count(product, duration)} keys left\n\n"
        caption += f"📲 *UPI ID:* `q542401897@ybl`\n\n"
        caption += f"*Scan QR or Pay & Click 'I have paid'*\n"
        caption += f"🔑 *Key will be delivered INSTANTLY after payment verification!*"
        
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=payment_kb(order_id))
        
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired or already processed!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Admin notified! Key will be delivered shortly.")
        
        bot.send_message(ADMIN_ID, f"🔔 *PAYMENT CLAIM*\n\n👤 @{uname}\n📦 {PRODUCTS[o['product']]['name']}\n⏱️ {o['duration']}\n💰 ₹{o['amount']}\n🆔 `{order_id}`\n✅ Stock available: {get_stock_count(o['product'], o['duration'])} keys", parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("approve_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only admin can approve!")
            return
        
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired or already processed!")
            return
        
        o = pending_orders[order_id]
        
        # Check stock again before delivering
        if get_stock_count(o['product'], o['duration']) == 0:
            bot.send_message(ADMIN_ID, f"⚠️ *STOCK ALERT*\n\n{o['product']} - {o['duration']} is OUT OF STOCK!\nPlease add keys first.")
            bot.answer_callback_query(call.id, "❌ Stock is empty! Add keys first.")
            return
        
        # Get key from stock
        key = pop_key(o['product'], o['duration'])
        
        if not key:
            bot.send_message(ADMIN_ID, f"⚠️ *STOCK ERROR*\n\nNo key available for {o['product']} - {o['duration']}")
            bot.answer_callback_query(call.id, "❌ Key delivery failed! No stock.")
            return
        
        # Save to user
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        
        # Save order
        db["orders"].append({
            "username": o['username'],
            "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'],
            "amount": o['amount'],
            "key": key,
            "date": datetime.datetime.now().strftime("%d %b %Y")
        })
        
        # Send key to user
        bot.send_message(user_cid, f"✅ *KEY DELIVERED!*\n\n📦 {PRODUCTS[o['product']]['name']}\n⏱️ {o['duration']}\n💰 ₹{o['amount']}\n\n🔑 *Your License Key:*\n`{key}`\n\n💡 *How to use:*\n1. Copy the key\n2. Open {PRODUCTS[o['product']]['name']}\n3. Enter the key\n4. Enjoy Premium!\n\nThank you for choosing Reddy Premium! 👑", parse_mode="Markdown", reply_markup=main_menu())
        
        # Notify admin
        remaining = get_stock_count(o['product'], o['duration'])
        bot.send_message(ADMIN_ID, f"✅ *ORDER COMPLETED*\n\n👤 @{o['username']}\n📦 {PRODUCTS[o['product']]['name']}\n⏱️ {o['duration']}\n💰 ₹{o['amount']}\n🔑 `{key}`\n📊 Remaining stock: {remaining} keys", parse_mode="Markdown")
        
        bot.answer_callback_query(call.id, "✅ Key delivered successfully!")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("reject_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Only admin!")
            return
        
        bot.send_message(user_cid, "❌ *Payment verification failed.*\nPlease contact support or try again.", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Payment rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ Order Cancelled", reply_markup=None)
    
    elif data == "my_keys":
        uid_str = str(call.from_user.id)
        keys_list = db["users"].get(uid_str, {}).get("keys", [])
        if not keys_list:
            bot.edit_message_text("🔑 *MY PURCHASED KEYS*\n\n🔑 No keys purchased yet.\n\n🛒 Use Purchase option to buy premium keys!", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            msg = "🔑 *YOUR PURCHASED KEYS*\n\n"
            for k in keys_list[-5:]:
                msg += f"📦 *{k['product']}* ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n\n"
            msg += f"\n{'-'*30}\n⚠️ Keep your keys private!\n🚫 Do not share with anyone."
            bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "support":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact Support", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("📊 Check Stock", callback_data="stock_status"))
        kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
        bot.edit_message_text("🆘 *PREMIUM SUPPORT*\n\n💬 24/7 Assistance\n⚡ Instant Response\n❤️ Dedicated Team\n\nClick below to contact support:", cid, call.message.id, parse_mode="Markdown", reply_markup=kb)

def back_menu_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb

def expire_order(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order Expired!*\n\nYour order has been cancelled due to inactivity.\nPlease start a new purchase.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API ROUTES
# ============================================================

@app.route('/')
def home():
    total_keys = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    return jsonify({"bot": "@ReddyBot", "status": "Bot is running!", "total_keys": total_keys})

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
    return jsonify({"success": True, "added": len(keys_list)})

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

@app.route('/api/users/key', methods=['POST'])
def api_user_key():
    data = request.json
    uid = str(data.get('user_id'))
    if uid not in db["users"]:
        db["users"][uid] = {"username": data.get('username'), "keys": []}
    db["users"][uid]["keys"].append({
        "product": data.get('product'),
        "duration": data.get('duration'),
        "key": data.get('key'),
        "date": datetime.datetime.now().strftime("%d %b %Y")
    })
    return jsonify({"success": True})

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
    print("🤖 REDDY PREMIUM BOT - WITH STOCK DISPLAY")
    print("=" * 50)
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ Stock Display: ENABLED")
    print(f"✅ Admin Panel: /admin")
    print("=" * 50)
    
    # Remove webhook and set new one
    bot.remove_webhook()
    
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    webhook_url = f"{render_url}/webhook"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set to: {webhook_url}")
    
    app.run(host='0.0.0.0', port=8080)

#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - RAZORPAY AUTO-PAYMENT (FULL AUTOMATION)
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
from flask import Flask, request, jsonify, send_from_directory

# ========== CONFIG ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"
DATA_FILE = "bot_data.json"

# Razorpay Credentials (Replace with your actual keys)
RAZORPAY_KEY_ID = "rzp_test_Swf7omML9UnAHQ"
RAZORPAY_KEY_SECRET = "70nCcG6l2fOXSijMSDB7UFuU"
RAZORPAY_WEBHOOK_SECRET = "MyRzpWebhookSecret@2024"  # from Razorpay Dashboard

# Initialize Razorpay Client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}  # For storing temporary order data

# Load data from file
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

SETUP_VIDEOS = {
    "deadeye": "https://youtu.be/example_deadeye",
    "vision": "https://youtu.be/example_vision",
    "rage": "https://youtu.be/example_rage",
    "winios": "https://youtu.be/example_winios",
    "kingios": "https://youtu.be/example_kingios",
}

SETUP_TEXT = {
    "deadeye": "1️⃣ Download Deadeye\n2️⃣ Install\n3️⃣ Enter key\n4️⃣ Activate",
    "vision": "1️⃣ Download Vision\n2️⃣ Run as admin\n3️⃣ Enter key\n4️⃣ Enjoy",
    "rage": "1️⃣ Extract Rage\n2️⃣ Run loader\n3️⃣ Enter key\n4️⃣ Launch game",
    "winios": "1️⃣ Install WinIOS\n2️⃣ Open as admin\n3️⃣ Paste key\n4️⃣ Restart",
    "kingios": "1️⃣ Download KingIOS\n2️⃣ Disable Defender\n3️⃣ Install\n4️⃣ Activate",
}

STICKERS = {
    "welcome": "✨👑",
    "buy": "🛒💎",
    "key": "🔑",
    "success": "🎉✅",
    "payment": "💳",
    "stock": "📦",
    "support": "💬",
    "setup": "🎥📺",
}

# ========== DATABASE HELPERS ==========
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
    """Create an order in Razorpay and return the checkout link"""
    try:
        # Amount should be in paise (multiply by 100)
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
        # Create a payment page/checkout link
        payment_link = f"https://rzp.io/l/{razorpay_order['id']}"  # Simplified, you can also use Razorpay Standard Checkout
        return payment_link, razorpay_order['id']
    except Exception as e:
        print(f"Razorpay order creation failed: {e}")
        return None, None

def verify_webhook_signature(body, signature):
    """Verify that webhook came from Razorpay"""
    try:
        expected_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False

def deliver_key_from_razorpay(order_id, payment_details):
    """Deliver key to user after successful payment verification"""
    # Retrieve pending order data
    if order_id not in pending_orders:
        return False
    
    o = pending_orders[order_id]
    
    # Check stock availability
    if get_stock(o['product'], o['duration']) == 0:
        # Notify admin about stockout
        bot.send_message(ADMIN_ID, f"⚠️ STOCK ALERT: {PRODUCTS[o['product']]['name']} - {o['duration']} is OUT OF STOCK!")
        return False
    
    # Fetch and deliver key
    key = pop_key(o['product'], o['duration'])
    if not key:
        return False
    
    # Save to user and orders
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
    
    # Send key to user
    setup_link = SETUP_VIDEOS.get(o['product'], "https://t.me/ReddyHack")
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

🎥 *Need setup help?* [Watch Tutorial]({setup_link})

⚠️ Keep private, do not share.

👑 Thank you for choosing Reddy Premium!"""
    
    bot.send_message(o['chat_id'], user_msg, parse_mode="Markdown", reply_markup=main_menu())
    
    # Cleanup
    del pending_orders[order_id]
    return True

# ========== TELEGRAM KEYBOARDS ==========
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{STICKERS['buy']} Buy", callback_data="buy"),
        InlineKeyboardButton(f"{STICKERS['key']} My Keys", callback_data="mykeys"),
        InlineKeyboardButton(f"{STICKERS['stock']} Stock", callback_data="stock"),
        InlineKeyboardButton(f"{STICKERS['setup']} Setup", callback_data="setup_menu"),
        InlineKeyboardButton(f"{STICKERS['support']} Support", callback_data="help"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        total = get_stock(key, "day") + get_stock(key, "week") + get_stock(key, "month")
        status = "✅" if total > 0 else "❌"
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} {status}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
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
    
    kb.add(InlineKeyboardButton(day_btn, callback_data=f"plan_{product}_day"))
    kb.add(InlineKeyboardButton(week_btn, callback_data=f"plan_{product}_week"))
    kb.add(InlineKeyboardButton(month_btn, callback_data=f"plan_{product}_month"))
    kb.add(InlineKeyboardButton(f"{STICKERS['setup']} Setup Guide", callback_data=f"setup_{product}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
    return kb

def setup_all_products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"setup_{key}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
    return kb

# ========== TELEGRAM BOT HANDLERS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    text = f"""{STICKERS['welcome']} *REDDY PREMIUM* {STICKERS['welcome']}

Hello {msg.from_user.first_name}!

💎 Trusted License Shop
⚡ Instant Delivery
🛡️ 100% Genuine
🎥 Setup guides included!

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
        bot.edit_message_text(f"{STICKERS['buy']} *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data_cb == "stock":
        text = f"{STICKERS['stock']} *Stock Available*\n\n"
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
            text = f"{STICKERS['key']} *My Keys*\n\nYou have no keys yet.\nUse Buy option."
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = f"{STICKERS['key']} *Your Keys*\n\n"
            for k in user_keys[-5:][::-1]:
                prod_key = None
                for pid, pdata in PRODUCTS.items():
                    if pdata['name'].lower() == k['product'].lower():
                        prod_key = pid
                        break
                text += f"📦 {k['product']} ({k['duration']})\n🔑 `{k['key']}`\n📅 {k['date']}\n"
                if prod_key and prod_key in SETUP_VIDEOS:
                    text += f"🎥 [Setup Guide]({SETUP_VIDEOS[prod_key]})\n"
                text += "\n"
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data_cb == "setup_menu":
        text = f"{STICKERS['setup']} *Setup Guides*\n\nSelect a product to view its setup tutorial:"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=setup_all_products_kb())
    
    elif data_cb.startswith("setup_"):
        product = data_cb.split("_")[1]
        if product in SETUP_VIDEOS:
            text = f"🎥 *{PRODUCTS[product]['name']} Setup Guide*\n\n"
            text += f"📹 *Video Tutorial:*\n{SETUP_VIDEOS[product]}\n\n"
            text += f"📝 *Step-by-Step:*\n{SETUP_TEXT.get(product, 'Follow the video instructions.')}\n\n"
            text += "💡 *Need help?* Contact @ReddyHack"
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("◀️ Back to Setup Menu", callback_data="setup_menu"))
            kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="back"))
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
        else:
            bot.answer_callback_query(call.id, "Setup guide coming soon!", show_alert=True)
    
    elif data_cb == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("🎥 Setup Guides", callback_data="setup_menu"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
        text = f"{STICKERS['support']} *Support*\n\n📞 @ReddyHack\n24/7 Available\n\nAlso check our setup guides for help."
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif data_cb.startswith("prod_"):
        product = data_cb.split("_")[1]
        p = PRODUCTS[product]
        text = f"{p['emoji']} *{p['name']}*\n\n💰 *Prices*\n"
        text += f"🟢 1 Day - ₹{PRICES[product]['day']}\n"
        text += f"🟡 7 Days - ₹{PRICES[product]['week']}\n"
        text += f"🔴 30 Days - ₹{PRICES[product]['month']}\n\n"
        text += "✅ Choose your plan or view Setup Guide 👇"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    
    elif data_cb.startswith("plan_"):
        _, product, duration = data_cb.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Sold out! Choose another.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        
        # Create Razorpay Order and get payment link
        payment_link, razorpay_order_id = create_razorpay_order(amount, order_id, product, duration)
        
        if not payment_link:
            bot.answer_callback_query(call.id, "❌ Payment gateway error! Please try again later.", show_alert=True)
            return
        
        # Store pending order data
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid,
            "razorpay_order_id": razorpay_order_id
        }
        
        # Send payment link and instructions
        caption = f"""{STICKERS['payment']} *RAZORPAY PAYMENT* {STICKERS['payment']}

🆔 *Order:* `{order_id}`
📦 *Product:* {PRODUCTS[product]['name']}
⏱️ *Duration:* {duration}
💰 *Amount:* ₹{amount}

━━━━━━━━━━━━━━━━━━━━━━
🔗 *Click below to pay securely:*

👉 [PAY NOW - Razorpay]({payment_link})

━━━━━━━━━━━━━━━━━━━━━━
✅ *After payment, key will be sent automatically*
🔑 *No manual approval needed!*
⏳ *Complete payment within 15 minutes*
"""
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💳 PAY NOW", url=payment_link))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
        
        bot.delete_message(cid, call.message.id)
        bot.send_message(cid, caption, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
        
        # Auto-expire after 15 minutes
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

# ========== RAZORPAY WEBHOOK HANDLER ==========
@app.route('/razorpay_webhook', methods=['POST'])
def razorpay_webhook():
    # Verify webhook signature
    signature = request.headers.get('X-Razorpay-Signature')
    if not signature or not verify_webhook_signature(request.get_data(as_text=True), signature):
        return jsonify({"error": "Invalid signature"}), 400
    
    # Parse webhook data
    webhook_data = request.json
    event = webhook_data.get('event')
    
    if event == 'payment.captured':
        payment_data = webhook_data.get('payload', {}).get('payment', {}).get('entity', {})
        order_id_from_razorpay = payment_data.get('order_id')
        
        # Find our internal order ID from the Razorpay order ID
        internal_order_id = None
        for oid, order_data in pending_orders.items():
            if order_data.get('razorpay_order_id') == order_id_from_razorpay:
                internal_order_id = oid
                break
        
        if internal_order_id:
            deliver_key_from_razorpay(internal_order_id, payment_data)
        else:
            # Order might have expired, log it
            print(f"Order not found for Razorpay order: {order_id_from_razorpay}")
    
    return jsonify({"status": "ok"}), 200

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
    print("🤖 REDDY BOT - RAZORPAY AUTO-PAYMENT")
    print("=" * 50)
    print("✅ Payment Gateway: Razorpay (Fully Automated)")
    print("✅ Stock Display: Enabled")
    print("✅ Setup Guides: Enabled")
    print("=" * 50)
    
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

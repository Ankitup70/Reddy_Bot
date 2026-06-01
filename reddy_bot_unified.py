#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - PERSISTENT STORAGE WITH MONGODB
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
from pymongo import MongoClient
from bson.objectid import ObjectId

# ========== CONFIG ==========
BOT_TOKEN = "8646356913:AAHqS40oeDQQPZRik2GYcE0nAjyQfdo5QVo"
ADMIN_ID = "1648621649"

# 🔴 REPLACE WITH YOUR MONGODB CONNECTION STRING 🔴
MONGO_URI = "mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "reddy_premium"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
products_col = db["products"]
keys_col = db["keys"]
users_col = db["users"]
orders_col = db["orders"]
stats_col = db["stats"]

# Initialize default data
if products_col.count_documents({}) == 0:
    default_products = {
        "deadeye": {"name": "Deadeye", "emoji": "🎯"},
        "vision": {"name": "Vision", "emoji": "👁️"},
        "rage": {"name": "Rage", "emoji": "⚡"},
        "winios": {"name": "WinIOS", "emoji": "💻"},
        "kingios": {"name": "KingIOS", "emoji": "👑"},
    }
    for pid, p in default_products.items():
        products_col.insert_one({"_id": pid, **p})

if keys_col.count_documents({}) == 0:
    for pid in ["deadeye","vision","rage","winios","kingios"]:
        keys_col.insert_one({"_id": pid, "day": [], "week": [], "month": []})

if stats_col.count_documents({}) == 0:
    stats_col.insert_one({"_id": "stats", "total_revenue": 0, "total_orders": 0})

# Prices (static, can be moved to DB if needed)
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

PRODUCTS = {doc["_id"]: {"name": doc["name"], "emoji": doc["emoji"]} for doc in products_col.find()}

# Helper functions using MongoDB
def get_stock(product, duration):
    doc = keys_col.find_one({"_id": product})
    if doc:
        return len(doc.get(duration, []))
    return 0

def pop_key(product, duration):
    doc = keys_col.find_one({"_id": product})
    if not doc:
        return None
    pool = doc.get(duration, [])
    if pool:
        key = pool.pop(0)
        keys_col.update_one({"_id": product}, {"$set": {duration: pool}})
        return key
    return None

def add_keys_to_db(product, duration, key_list):
    doc = keys_col.find_one({"_id": product})
    if not doc:
        keys_col.insert_one({"_id": product, "day": [], "week": [], "month": []})
        doc = keys_col.find_one({"_id": product})
    current = doc.get(duration, [])
    current.extend(key_list)
    keys_col.update_one({"_id": product}, {"$set": {duration: current}})

def save_user_key(user_id, username, product_name, duration, key):
    uid = str(user_id)
    user_doc = users_col.find_one({"_id": uid})
    if not user_doc:
        users_col.insert_one({"_id": uid, "username": username, "keys": []})
        user_doc = users_col.find_one({"_id": uid})
    keys_list = user_doc.get("keys", [])
    keys_list.append({
        "product": product_name,
        "duration": duration,
        "key": key,
        "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
    })
    users_col.update_one({"_id": uid}, {"$set": {"keys": keys_list, "username": username}})

def save_order(order_data):
    orders_col.insert_one(order_data)
    stats_col.update_one({"_id": "stats"}, {"$inc": {"total_orders": 1, "total_revenue": order_data.get("amount", 0)}})

def get_all_keys():
    return {doc["_id"]: {"day": doc.get("day",[]), "week": doc.get("week",[]), "month": doc.get("month",[])} for doc in keys_col.find()}

def get_all_users():
    return {doc["_id"]: {"username": doc.get("username",""), "keys": doc.get("keys",[])} for doc in users_col.find()}

def get_all_orders():
    return list(orders_col.find().sort("_id", -1))

def get_stats():
    stat = stats_col.find_one({"_id": "stats"})
    if not stat:
        return {"total_orders": 0, "total_revenue": 0}
    return stat

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

# ========== KEYBOARDS (unchanged) ==========
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

def pay_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I have paid", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, uid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ok_{order_id}_{uid}"))
    kb.add(InlineKeyboardButton("❌ Reject", callback_data=f"no_{order_id}_{uid}"))
    return kb

def setup_all_products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"setup_{key}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
    return kb

# ========== BOT HANDLERS ==========
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}

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
    data = call.data

    if data == "back":
        bot.edit_message_text("👇 *Main Menu*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "buy":
        bot.edit_message_text(f"{STICKERS['buy']} *Select Product*", cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "stock":
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
    
    elif data == "mykeys":
        uid_str = str(uid)
        user_doc = users_col.find_one({"_id": uid_str})
        keys = user_doc.get("keys", []) if user_doc else []
        if not keys:
            text = f"{STICKERS['key']} *My Keys*\n\nYou have no keys yet.\nUse Buy option."
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = f"{STICKERS['key']} *Your Keys*\n\n"
            for k in keys[-5:][::-1]:
                # find product id for setup link
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
    
    elif data == "setup_menu":
        text = f"{STICKERS['setup']} *Setup Guides*\n\nSelect a product to view its setup tutorial:"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=setup_all_products_kb())
    
    elif data.startswith("setup_"):
        product = data.split("_")[1]
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
    
    elif data == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 Contact", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("🎥 Setup Guides", callback_data="setup_menu"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
        text = f"{STICKERS['support']} *Support*\n\n📞 @ReddyHack\n24/7 Available\n\nAlso check our setup guides for help."
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        text = f"{p['emoji']} *{p['name']}*\n\n💰 *Prices*\n"
        text += f"🟢 1 Day - ₹{PRICES[product]['day']}\n"
        text += f"🟡 7 Days - ₹{PRICES[product]['week']}\n"
        text += f"🔴 30 Days - ₹{PRICES[product]['month']}\n\n"
        text += "✅ Choose your plan or view Setup Guide 👇"
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    
    elif data.startswith("plan_"):
        _, product, duration = data.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Sold out! Choose another.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"R{int(time.time())}{random.randint(10,99)}"
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_qr(amount, order_id)
        caption = f"""{STICKERS['payment']} *ORDER #{order_id}*

📦 {PRODUCTS[product]['name']}
⏱️ {duration}
💰 ₹{amount}

━━━━━━━━━━
📲 UPI: `q542401897@ybl`

✅ Pay & tap *I have paid*
🔑 Key will be sent instantly
━━━━━━━━━━
"""
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=pay_kb(order_id))
        threading.Timer(900, lambda: expire(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Expired!")
            return
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Notified admin!")
        admin_msg = f"""🔔 *Payment Claim*

👤 @{uname}
📦 {PRODUCTS[o['product']]['name']}
⏱️ {o['duration']}
💰 ₹{o['amount']}
🆔 {order_id}

✅ Verify & Approve"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("ok_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!")
            return
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Expired!")
            return
        o = pending_orders[order_id]
        if get_stock(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "No stock!")
            return
        key = pop_key(o['product'], o['duration'])
        if not key:
            bot.answer_callback_query(call.id, "Error!")
            return
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        save_order({
            "username": o['username'], "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'], "amount": o['amount'], "key": key,
            "date": datetime.datetime.now().strftime("%d %b %Y %I:%M %p")
        })
        setup_link = SETUP_VIDEOS.get(o['product'], "https://t.me/ReddyHack")
        user_msg = f"""{STICKERS['success']} *PAYMENT VERIFIED* {STICKERS['success']}

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
        bot.send_message(user_cid, user_msg, parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "✅ Key sent!")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("no_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "Admin only!")
            return
        bot.send_message(user_cid, "❌ *Payment not verified*\nContact @ReddyHack", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "Rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ Cancelled", reply_markup=None)
        bot.send_message(cid, "🔄 Start again 👇", reply_markup=main_menu())

def expire(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, "⌛ *Order expired*\nPlease start fresh.", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ========== FLASK API FOR ADMIN PANEL (using MongoDB) ==========
@app.route('/')
def home():
    return jsonify({"status": "online", "database": "MongoDB"})

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
        "total_users": users_col.count_documents({}),
        "total_revenue": stats["total_revenue"]
    })

@app.route('/api/keys/all')
def keys_all():
    return jsonify(get_all_keys())

@app.route('/api/keys/<product>/<duration>')
def get_keys(product, duration):
    doc = keys_col.find_one({"_id": product})
    keys = doc.get(duration, []) if doc else []
    return jsonify({"keys": keys})

@app.route('/api/keys', methods=['POST'])
def add_keys():
    data = request.json
    product = data['product']
    duration = data['duration']
    key_list = data['keys']
    add_keys_to_db(product, duration, key_list)
    return jsonify({"ok": True})

@app.route('/api/keys/generate', methods=['POST'])
def gen_keys():
    data = request.json
    product = data['product']
    duration = data['duration']
    count = data['count']
    prefix = PREFIX.get(product, "KEY")
    def g():
        return f"{prefix}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}-{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789',k=4))}"
    new_keys = [g() for _ in range(count)]
    add_keys_to_db(product, duration, new_keys)
    return jsonify({"ok": True})

@app.route('/api/keys/<product>/<duration>', methods=['DELETE'])
def clear_keys(product, duration):
    keys_col.update_one({"_id": product}, {"$set": {duration: []}})
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
    return jsonify(get_all_orders())

@app.route('/api/orders', methods=['DELETE'])
def del_orders():
    orders_col.delete_many({})
    stats_col.update_one({"_id": "stats"}, {"$set": {"total_orders": 0, "total_revenue": 0}})
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
    print("🤖 REDDY BOT - MONGODB PERSISTENT STORAGE")
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

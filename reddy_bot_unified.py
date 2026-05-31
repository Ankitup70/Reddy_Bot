#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - ULTRA PREMIUM EDITION
Glassmorphism Design | Animated Messages | Premium Look
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
    "deadeye": {"name": "✨ Deadeye", "emoji": "🎯", "prefix": "DEAD", "color": "#7c3aed", "bg": "🎯"},
    "vision": {"name": "👁️ Vision Pro", "emoji": "👁️", "prefix": "VIS", "color": "#3b82f6", "bg": "👁️"},
    "rage": {"name": "⚡ Rage Elite", "emoji": "⚡", "prefix": "RAGE", "color": "#ef4444", "bg": "⚡"},
    "winios": {"name": "💻 WinIOS", "emoji": "💻", "prefix": "WIN", "color": "#10b981", "bg": "💻"},
    "kingios": {"name": "👑 KingIOS", "emoji": "👑", "prefix": "KING", "color": "#f59e0b", "bg": "👑"},
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
    try:
        return len(db["keys"].get(product, {}).get(duration, []))
    except:
        return 0

def get_stock_status(product, duration):
    count = get_stock_count(product, duration)
    if count == 0:
        return "❌ OUT OF STOCK"
    elif count < 5:
        return f"⚠️ ONLY {count} LEFT! 🔥"
    elif count < 20:
        return f"✅ {count} IN STOCK"
    else:
        return f"💎 {count} AVAILABLE"

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
# PREMIUM KEYBOARDS
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒✨ PURCHASE NOW", callback_data="purchase"),
        InlineKeyboardButton("🔑💎 MY KEYS", callback_data="my_keys"),
        InlineKeyboardButton("📊📈 STOCK STATUS", callback_data="stock_status"),
        InlineKeyboardButton("🆘👑 PREMIUM SUPPORT", callback_data="support"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        total_stock = get_stock_count(key, "day") + get_stock_count(key, "week") + get_stock_count(key, "month")
        if total_stock > 50:
            stock_icon = "🔥🔥🔥"
        elif total_stock > 10:
            stock_icon = "✅"
        elif total_stock > 0:
            stock_icon = "⚠️"
        else:
            stock_icon = "❌"
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} {stock_icon}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    return kb

def duration_kb(product):
    p = PRODUCTS[product]
    prices = PRICES[product]
    kb = InlineKeyboardMarkup(row_width=1)
    
    day_stock = get_stock_count(product, "day")
    week_stock = get_stock_count(product, "week")
    month_stock = get_stock_count(product, "month")
    
    day_text = f"🟢 24 HOURS - ₹{prices['day']}  {get_stock_status(product, 'day')}"
    week_text = f"🟡 7 DAYS - ₹{prices['week']}  {get_stock_status(product, 'week')}"
    month_text = f"🔴 30 DAYS - ₹{prices['month']}  {get_stock_status(product, 'month')}"
    
    if day_stock == 0:
        day_text = f"🟢 24 HOURS - ₹{prices['day']}  ❌ SOLD OUT"
    if week_stock == 0:
        week_text = f"🟡 7 DAYS - ₹{prices['week']}  ❌ SOLD OUT"
    if month_stock == 0:
        month_text = f"🔴 30 DAYS - ₹{prices['month']}  ❌ SOLD OUT"
    
    kb.add(InlineKeyboardButton(day_text, callback_data=f"dur_{product}_day"))
    kb.add(InlineKeyboardButton(week_text, callback_data=f"dur_{product}_week"))
    kb.add(InlineKeyboardButton(month_text, callback_data=f"dur_{product}_month"))
    kb.add(InlineKeyboardButton("◀️ BACK TO PRODUCTS", callback_data="purchase"))
    
    return kb

def payment_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I HAVE PAID ✅", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ CANCEL ORDER", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ APPROVE & DELIVER KEY ✅", callback_data=f"approve_{order_id}_{user_id}"))
    kb.add(InlineKeyboardButton("❌ REJECT PAYMENT", callback_data=f"reject_{order_id}_{user_id}"))
    return kb

# ============================================================
# PREMIUM MESSAGES
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    welcome_msg = f"""
╔══════════════════════════════════╗
║      👑 REDDY PREMIUM 👑         ║
╠══════════════════════════════════╣
║  ✨ PREMIUM LICENSE SHOP ✨       ║
║  💎 100% TRUSTED & VERIFIED      ║
║  ⚡ INSTANT DIGITAL DELIVERY      ║
║  🛡️ SECURE PAYMENT PROTECTED      ║
╠══════════════════════════════════╣
║  📊 LIVE STOCK AVAILABLE          ║
║  🔥 LIMITED KEYS - GRAB NOW!      ║
╚══════════════════════════════════╝

✨ *WELCOME TO REDDY PREMIUM* ✨

💎 *Why Choose Us?*
┌─────────────────────────────────┐
│ ✓ 100% Genuine License Keys     │
│ ✓ Instant Auto Delivery          │
│ ✓ 24/7 Premium Support           │
│ ✓ Best Price Guarantee           │
│ ✓ Secure Payment Gateway         │
└─────────────────────────────────┘

🔥 *HOT DEALS AVAILABLE!* 🔥

👇 *TAP BELOW TO START* 👇
"""
    bot.send_message(msg.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "main_menu":
        bot.edit_message_text("✨ *MAIN MENU* ✨\n\nChoose an option below:", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "purchase":
        msg = """
╔════════════════════════╗
║    🛒 SELECT PRODUCT    ║
╠════════════════════════╣
║  🎯 DEADEYE - Pro Aim   ║
║  👁️ VISION - ESP Hack   ║
║  ⚡ RAGE - Aimbot       ║
║  💻 WINIOS - iOS/PC     ║
║  👑 KINGIOS - Ultimate  ║
╚════════════════════════╝

📦 *Choose your premium product below:*
"""
        bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "stock_status":
        stock_msg = """
╔════════════════════════════════════╗
║      📊 LIVE STOCK STATUS 📊       ║
╠════════════════════════════════════╣
"""
        for key, p in PRODUCTS.items():
            day = get_stock_count(key, "day")
            week = get_stock_count(key, "week")
            month = get_stock_count(key, "month")
            total = day + week + month
            
            if total > 50:
                bar = "🟢🟢🟢🟢🟢"
            elif total > 20:
                bar = "🟢🟢🟢🟡🟡"
            elif total > 5:
                bar = "🟢🟡🟡🟡🔴"
            elif total > 0:
                bar = "🟡🔴🔴🔴🔴"
            else:
                bar = "🔴🔴🔴🔴🔴"
            
            stock_msg += f"""
║  {p['emoji']} *{p['name']}*
║  {bar}
║  🟢 Day: {day} keys  🟡 Week: {week} keys  🔴 Month: {month} keys
║  ─────────────────────────────────
"""
        stock_msg += """
║  🔥 *GRAB BEFORE STOCK ENDS!* 🔥
╚════════════════════════════════════╝
"""
        bot.edit_message_text(stock_msg, cid, call.message.id, parse_mode="Markdown", reply_markup=back_menu_kb())
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        stock_msg = f"""
╔════════════════════════════════╗
║     {p['emoji']} {p['name']} {p['emoji']}      ║
╠════════════════════════════════╣
║  🟢 DAY PLAN   - ₹{PRICES[product]['day']}
║      ├ Stock: {get_stock_status(product, 'day')}
║  🟡 WEEK PLAN  - ₹{PRICES[product]['week']}
║      ├ Stock: {get_stock_status(product, 'week')}
║  🔴 MONTH PLAN - ₹{PRICES[product]['month']}
║      ├ Stock: {get_stock_status(product, 'month')}
╠════════════════════════════════╣
║  ✅ *PAY & GET INSTANT KEY*     ║
║  🔑 *100% WORKING GUARANTEE*    ║
╚════════════════════════════════╝

✨ *Choose your duration below:* ✨
"""
        bot.edit_message_text(stock_msg, cid, call.message.id, parse_mode="Markdown", reply_markup=duration_kb(product))
    
    elif data.startswith("dur_"):
        _, product, duration = data.split("_")
        
        if get_stock_count(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ SOLD OUT! Please choose another plan.", show_alert=True)
            return
        
        amount = PRICES[product][duration]
        order_id = f"REDDY{int(time.time())}{random.randint(100,999)}"
        
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid
        }
        
        qr = make_upi_qr(amount, order_id)
        
        caption = f"""
╔════════════════════════════════════╗
║         🛒 ORDER SUMMARY 🛒        ║
╠════════════════════════════════════╣
║  🆔 ORDER ID: `{order_id}`
║  📦 PRODUCT: {PRODUCTS[product]['name']}
║  ⏱️ DURATION: {duration.upper()}
║  💰 AMOUNT: ₹{amount}
║  ✅ STOCK: {get_stock_status(product, duration)}
╠════════════════════════════════════╣
║  📲 UPI ID: `q542401897@ybl`
║  👤 NAME: Reddy Premium
╠════════════════════════════════════╣
║  🔑 *KEY WILL BE DELIVERED AFTER*  ║
║  ✅ *PAYMENT VERIFICATION*         ║
╚════════════════════════════════════╝

✨ *SCAN QR CODE OR PAY VIA UPI* ✨
💎 *CLICK "I HAVE PAID" AFTER PAYMENT*
"""
        
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=payment_kb(order_id))
        
        threading.Timer(900, lambda: expire_order(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "⌛ Order expired!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Payment claim sent to admin!")
        
        admin_msg = f"""
╔════════════════════════════════╗
║      🔔 NEW PAYMENT CLAIM      ║
╠════════════════════════════════╣
║  👤 USER: @{uname}
║  🆔 ID: `{uid}`
║  📦 PRODUCT: {PRODUCTS[o['product']]['name']}
║  ⏱️ DURATION: {o['duration']}
║  💰 AMOUNT: ₹{o['amount']}
║  🆔 ORDER: `{order_id}`
╠════════════════════════════════╣
║  ✅ VERIFY PAYMENT IN UPI APP   ║
║  🔑 THEN APPROVE TO DELIVER KEY ║
╚════════════════════════════════╝
"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("approve_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin only!")
            return
        
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order expired!")
            return
        
        o = pending_orders[order_id]
        
        if get_stock_count(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "❌ Stock empty! Add keys first.")
            return
        
        key = pop_key(o['product'], o['duration'])
        
        if not key:
            bot.answer_callback_query(call.id, "❌ Key delivery failed!")
            return
        
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        
        db["orders"].append({
            "username": o['username'],
            "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'],
            "amount": o['amount'],
            "key": key,
            "date": datetime.datetime.now().strftime("%d %b %Y")
        })
        
        delivery_msg = f"""
╔══════════════════════════════════════╗
║         ✅ KEY DELIVERED ✅          ║
╠══════════════════════════════════════╣
║  📦 PRODUCT: {PRODUCTS[o['product']]['name']}
║  ⏱️ DURATION: {o['duration']}
║  💰 AMOUNT: ₹{o['amount']}
╠══════════════════════════════════════╣
║  🔑 *YOUR LICENSE KEY:*              ║
║  `{key}`
╠══════════════════════════════════════╣
║  📌 *HOW TO ACTIVATE:*               ║
║  1. Copy the key above               ║
║  2. Open {PRODUCTS[o['product']]['name']}
║  3. Paste & Activate                 ║
║  4. Enjoy Premium! 🎉                ║
╠══════════════════════════════════════╣
║  👑 THANK YOU FOR CHOOSING           ║
║  REDDY PREMIUM! 💎                   ║
╚══════════════════════════════════════╝

✨ *Need help? Contact @ReddyHack* ✨
"""
        bot.send_message(user_cid, delivery_msg, parse_mode="Markdown", reply_markup=main_menu())
        
        remaining = get_stock_count(o['product'], o['duration'])
        bot.send_message(ADMIN_ID, f"✅ ORDER COMPLETED! Remaining stock: {remaining} keys")
        
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
        
        bot.send_message(user_cid, "❌ *PAYMENT NOT VERIFIED*\n\nPlease contact support for assistance.", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Payment rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ *ORDER CANCELLED*", reply_markup=None)
        bot.send_message(cid, "🔄 *Start new purchase from main menu*", parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "my_keys":
        uid_str = str(call.from_user.id)
        keys_list = db["users"].get(uid_str, {}).get("keys", [])
        if not keys_list:
            msg = """
╔════════════════════════════╗
║      🔑 MY KEYS 🔑         ║
╠════════════════════════════╣
║  ❌ NO KEYS FOUND           ║
╠════════════════════════════╣
║  🛒 PURCHASE NOW TO GET     ║
║  🔥 PREMIUM ACCESS          ║
╚════════════════════════════╝
"""
            bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            msg = """
╔════════════════════════════╗
║      🔑 MY KEYS 🔑         ║
╠════════════════════════════╣
"""
            for k in keys_list[-5:]:
                msg += f"""
║  📦 {k['product']}
║  ⏱️ {k['duration']}
║  🔑 `{k['key']}`
║  📅 {k['date']}
║  ─────────────────────────
"""
            msg += """
╚════════════════════════════╝
⚠️ *KEEP YOUR KEYS PRIVATE!*
🚫 *DO NOT SHARE WITH ANYONE*
"""
            bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "support":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 CONTACT SUPPORT", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("📊 CHECK STOCK", callback_data="stock_status"))
        kb.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
        msg = """
╔════════════════════════════╗
║      🆘 PREMIUM SUPPORT    ║
╠════════════════════════════╣
║  💬 24/7 LIVE ASSISTANCE    ║
║  ⚡ INSTANT RESPONSE        ║
║  ❤️ DEDICATED TEAM          ║
╠════════════════════════════╣
║  👑 @ReddyHack              ║
╚════════════════════════════╝

✨ *Click below to contact support* ✨
"""
        bot.edit_message_text(msg, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)

def back_menu_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))
    return kb

def expire_order(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, """
╔════════════════════════════╗
║      ⌛ ORDER EXPIRED       ║
╠════════════════════════════╣
║  Time limit exceeded.      ║
║  Please start fresh        ║
║  purchase from main menu.  ║
╚════════════════════════════╝
""", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API ROUTES
# ============================================================

@app.route('/')
def home():
    total_keys = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    return jsonify({"bot": "@ReddyPremiumBot", "status": "🟢 ONLINE", "total_keys": total_keys, "version": "4.0"})

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
    print("=" * 60)
    print("👑 REDDY PREMIUM BOT - ULTRA PREMIUM EDITION")
    print("=" * 60)
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ Premium UI: ENABLED")
    print(f"✅ Stock Display: ENABLED")
    print(f"✅ Admin Panel: /admin")
    print("=" * 60)
    
    bot.remove_webhook()
    
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    webhook_url = f"{render_url}/webhook"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set to: {webhook_url}")
    
    app.run(host='0.0.0.0', port=8080)

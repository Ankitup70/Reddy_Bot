#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - ULTRA PREMIUM WITH STICKERS
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

# Premium Stickers for each product
STICKERS = {
    "welcome": "CAACAgIAAxkBAAEBHftl7X3jPwADeQIAApKtUAsAAaU-Tfa_DAWkHgQ",
    "deadeye": "🎯",
    "vision": "👁️",
    "rage": "⚡",
    "winios": "💻",
    "kingios": "👑",
    "payment": "💳",
    "success": "✅",
    "key": "🔑",
}

PRODUCTS = {
    "deadeye": {"name": "Deadeye", "sticker": "🎯", "color": "⚡"},
    "vision": {"name": "Vision", "sticker": "👁️", "color": "🔮"},
    "rage": {"name": "Rage", "sticker": "⚡", "color": "🔥"},
    "winios": {"name": "WinIOS", "sticker": "💻", "color": "🪟"},
    "kingios": {"name": "KingIOS", "sticker": "👑", "color": "💎"},
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

def get_stock_emoji(count):
    if count == 0:
        return "🔴"
    elif count < 5:
        return "🟡"
    elif count < 20:
        return "🟢"
    else:
        return "💚"

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

def get_product_sticker(product):
    stickers = {
        "deadeye": "🎯⚡",
        "vision": "👁️🔮",
        "rage": "⚡🔥",
        "winios": "💻🪟",
        "kingios": "👑💎",
    }
    return stickers.get(product, "🎁")

# ============================================================
# KEYBOARDS - PREMIUM
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛍️ BUY NOW", callback_data="buy"),
        InlineKeyboardButton("🔑 MY KEYS", callback_data="mykeys"),
        InlineKeyboardButton("📊 STOCK", callback_data="stock"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="help"),
    )
    return kb

def products_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, p in PRODUCTS.items():
        stock_total = get_stock(key, "day") + get_stock(key, "week") + get_stock(key, "month")
        status = "✅" if stock_total > 0 else "🔴"
        kb.add(InlineKeyboardButton(f"{p['sticker']} {p['name']} {status}", callback_data=f"prod_{key}"))
    kb.add(InlineKeyboardButton("◀️ BACK", callback_data="back"))
    return kb

def plans_kb(product):
    kb = InlineKeyboardMarkup(row_width=1)
    prices = PRICES[product]
    
    day_stock = get_stock(product, "day")
    week_stock = get_stock(product, "week")
    month_stock = get_stock(product, "month")
    
    day_emoji = get_stock_emoji(day_stock)
    week_emoji = get_stock_emoji(week_stock)
    month_emoji = get_stock_emoji(month_stock)
    
    day_text = f"{day_emoji} 1 DAY - ₹{prices['day']}"
    week_text = f"{week_emoji} 7 DAYS - ₹{prices['week']}"
    month_text = f"{month_emoji} 30 DAYS - ₹{prices['month']}"
    
    if day_stock == 0:
        day_text = f"🔴 1 DAY - ₹{prices['day']} (SOLD OUT)"
    if week_stock == 0:
        week_text = f"🔴 7 DAYS - ₹{prices['week']} (SOLD OUT)"
    if month_stock == 0:
        month_text = f"🔴 30 DAYS - ₹{prices['month']} (SOLD OUT)"
    
    kb.add(InlineKeyboardButton(f"📅 {day_text}", callback_data=f"plan_{product}_day"))
    kb.add(InlineKeyboardButton(f"📅 {week_text}", callback_data=f"plan_{product}_week"))
    kb.add(InlineKeyboardButton(f"📅 {month_text}", callback_data=f"plan_{product}_month"))
    kb.add(InlineKeyboardButton("◀️ BACK", callback_data="back"))
    return kb

def pay_kb(order_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ I HAVE PAID", callback_data=f"paid_{order_id}"))
    kb.add(InlineKeyboardButton("❌ CANCEL", callback_data=f"cancel_{order_id}"))
    return kb

def admin_kb(order_id, uid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ APPROVE & SEND KEY", callback_data=f"ok_{order_id}_{uid}"))
    kb.add(InlineKeyboardButton("❌ REJECT", callback_data=f"no_{order_id}_{uid}"))
    return kb

# ============================================================
# PREMIUM MESSAGES WITH STICKERS
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    # Send welcome sticker
    try:
        bot.send_sticker(msg.chat.id, "CAACAgIAAxkBAAEBHftl7X3jPwADeQIAApKtUAsAAaU-Tfa_DAWkHgQ")
    except:
        pass
    
    text = f"""
╔══════════════════════════════════╗
║      👑 *REDDY PREMIUM* 👑       ║
╠══════════════════════════════════╣
║                                  ║
║   ✨ *Welcome {msg.from_user.first_name}!* ✨
║                                  ║
║   💎 *Premium License Shop*      ║
║   ⚡ *Instant Delivery*           ║
║   🛡️ *100% Genuine Keys*         ║
║                                  ║
╠══════════════════════════════════╣
║   🎯 *FEATURED PRODUCTS*         ║
║                                  ║
║   🎯 Deadeye - Pro Aim           ║
║   👁️ Vision - ESP Hack           ║
║   ⚡ Rage - Aimbot                ║
║   💻 WinIOS - iOS/PC Tools       ║
║   👑 KingIOS - Ultimate          ║
║                                  ║
╠══════════════════════════════════╣
║   🔥 *HOT OFFER* 🔥              ║
║   Buy any plan & get             ║
║   instant delivery!              ║
╚══════════════════════════════════╝

👇 *TAP BELOW TO START*
"""
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    if data == "back":
        bot.edit_message_text("👇 *Choose an option*", cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "buy":
        text = """
🛍️ *SELECT YOUR PRODUCT*
━━━━━━━━━━━━━━━━━━━━━━

Choose from our premium collection:

🎯 Deadeye - Ultimate Aim
👁️ Vision - ESP & Radar
⚡ Rage - Best Aimbot
💻 WinIOS - Multi Tool
👑 KingIOS - All in One

👇 *Click on product to see plans*
"""
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=products_kb())
    
    elif data == "stock":
        text = """
📊 *LIVE STOCK STATUS*
━━━━━━━━━━━━━━━━━━━━━━

"""
        for key, p in PRODUCTS.items():
            day = get_stock(key, "day")
            week = get_stock(key, "week")
            month = get_stock(key, "month")
            total = day + week + month
            
            if total > 20:
                bar = "🟢🟢🟢🟢🟢"
            elif total > 10:
                bar = "🟢🟢🟢🟡🟡"
            elif total > 0:
                bar = "🟢🟡🟡🔴🔴"
            else:
                bar = "🔴🔴🔴🔴🔴"
            
            text += f"{p['sticker']} *{p['name']}*\n"
            text += f"`{bar}`\n"
            text += f"📅 1D: {day}  |  7D: {week}  |  30D: {month}\n\n"
        
        text += """
━━━━━━━━━━━━━━━━━━━━━━
✅ *Order now for instant delivery*
🔑 *Limited keys available!*
"""
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "mykeys":
        uid_str = str(uid)
        keys = db["users"].get(uid_str, {}).get("keys", [])
        if not keys:
            text = """
🔑 *MY KEYS*
━━━━━━━━━━━━━━━━━━━━━━

📭 *No keys found*

🛍️ *Use BUY NOW option to purchase*
💎 *Get premium access today!*
"""
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            text = """
🔑 *YOUR PURCHASED KEYS*
━━━━━━━━━━━━━━━━━━━━━━

"""
            for k in keys[::-1][:5]:
                text += f"📦 *{k['product']}* ({k['duration']})\n"
                text += f"🔑 `{k['key']}`\n"
                text += f"📅 {k['date']}\n━━━━━━━━━━━━━━━━━━━━━━\n"
            text += """
⚠️ *Keep your keys private!*
🚫 *Do not share with anyone*
"""
            bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=main_menu())
    
    elif data == "help":
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📞 CONTACT SUPPORT", url="https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("📊 CHECK STOCK", callback_data="stock"))
        kb.add(InlineKeyboardButton("◀️ BACK", callback_data="back"))
        text = """
💬 *PREMIUM SUPPORT*
━━━━━━━━━━━━━━━━━━━━━━

🕐 *24/7 Available*
⚡ *Instant Response*
❤️ *Dedicated Team*

📞 *Contact:* @ReddyHack

*Feel free to reach out for:*
• Activation help
• Key issues
• Payment queries
• Technical support

━━━━━━━━━━━━━━━━━━━━━━
✨ *We're here to help!* ✨
"""
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=kb)
    
    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        sticker = get_product_sticker(product)
        text = f"""
{sticker} *{p['name']}* {sticker}
━━━━━━━━━━━━━━━━━━━━━━

💰 *PREMIUM PLANS*

🟢 *1 DAY PLAN*
   ├ Price: ₹{PRICES[product]['day']}
   ├ Validity: 24 Hours
   └ Stock: {get_stock(product, 'day')} keys

🟡 *7 DAYS PLAN*
   ├ Price: ₹{PRICES[product]['week']}
   ├ Validity: 7 Days
   └ Stock: {get_stock(product, 'week')} keys

🔴 *30 DAYS PLAN*
   ├ Price: ₹{PRICES[product]['month']}
   ├ Validity: 30 Days
   └ Stock: {get_stock(product, 'month')} keys

━━━━━━━━━━━━━━━━━━━━━━
✅ *Choose your plan below*
🔑 *Instant delivery guaranteed*
"""
        bot.edit_message_text(text, cid, call.message.id, parse_mode="Markdown", reply_markup=plans_kb(product))
    
    elif data.startswith("plan_"):
        parts = data.split("_")
        product = parts[1]
        duration = parts[2]
        
        stock = get_stock(product, duration)
        if stock == 0:
            bot.answer_callback_query(call.id, "❌ SOLD OUT! Please choose another plan.", show_alert=True)
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
💳 *ORDER #{order_id}*
━━━━━━━━━━━━━━━━━━━━━━

📦 *Product:* {PRODUCTS[product]['name']}
⏱️ *Duration:* {duration.upper()}
💰 *Amount:* ₹{amount}
✅ *Stock:* {stock} keys available

━━━━━━━━━━━━━━━━━━━━━━
📲 *UPI PAYMENT DETAILS*

`q542401897@ybl`
*Name:* Reddy Premium

━━━━━━━━━━━━━━━━━━━━━━
🔑 *After payment, tap "I HAVE PAID"*
⚡ *Key will be delivered instantly*

⏳ *Complete payment within 15 minutes*
"""
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption, parse_mode="Markdown", reply_markup=pay_kb(order_id))
        
        threading.Timer(900, lambda: expire(order_id, cid)).start()
    
    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "❌ Order expired!")
            return
        
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Payment claim sent! Key coming soon.")
        
        admin_msg = f"""
🔔 *NEW PAYMENT CLAIM*
━━━━━━━━━━━━━━━━━━━━━━

👤 *User:* @{uname}
🆔 *ID:* `{uid}`
📦 *Product:* {PRODUCTS[o['product']]['name']}
⏱️ *Duration:* {o['duration']}
💰 *Amount:* ₹{o['amount']}
🆔 *Order:* `{order_id}`

━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Verify payment in UPI app*
✅ *Click APPROVE to send key*
"""
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=admin_kb(order_id, cid))
    
    elif data.startswith("ok_"):
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
        
        if get_stock(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "❌ No stock! Add keys first.")
            return
        
        key = pop_key(o['product'], o['duration'])
        if not key:
            bot.answer_callback_query(call.id, "❌ Error!")
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
        
        sticker = get_product_sticker(o['product'])
        
        user_msg = f"""
╔══════════════════════════════════╗
║     ✅ PAYMENT VERIFIED ✅        ║
╠══════════════════════════════════╣
║                                  ║
║   🎉 *CONGRATULATIONS!* 🎉       ║
║                                  ║
║   Your order has been confirmed  ║
║   and your license key is ready! ║
║                                  ║
╠══════════════════════════════════╣
║  {sticker} *ORDER DETAILS* {sticker}
║                                  ║
║  📦 *Product:* {PRODUCTS[o['product']]['name']}
║  ⏱️ *Duration:* {o['duration']}
║  💰 *Amount:* ₹{o['amount']}
║                                  ║
╠══════════════════════════════════╣
║  🔑 *YOUR LICENSE KEY* 🔑        ║
║                                  ║
║  `{key}`                         ║
║                                  ║
╠══════════════════════════════════╣
║  📌 *HOW TO ACTIVATE* 📌         ║
║                                  ║
║  1️⃣ Copy the key above           ║
║  2️⃣ Open {PRODUCTS[o['product']]['name']}
║  3️⃣ Paste in license section     ║
║  4️⃣ Click Activate              ║
║  5️⃣ Enjoy Premium! 🚀           ║
║                                  ║
╠══════════════════════════════════╣
║  💡 *IMPORTANT NOTES*            ║
║  ⚠️ Keep this key private        ║
║  🚫 Do not share with anyone     ║
║  ✅ One device per license       ║
║                                  ║
╠══════════════════════════════════╣
║  👑 *Thank you for choosing*     ║
║  *REDDY PREMIUM!*                ║
║                                  ║
║  🌟 *Rate us:* @ReddyHack        ║
╚══════════════════════════════════╝

💎 *Need help? Contact @ReddyHack*
"""
        bot.send_message(user_cid, user_msg, parse_mode="Markdown", reply_markup=main_menu())
        
        remaining = get_stock(o['product'], o['duration'])
        bot.send_message(ADMIN_ID, f"✅ ORDER COMPLETED! {remaining} keys left for {PRODUCTS[o['product']]['name']}")
        
        bot.answer_callback_query(call.id, "✅ Key delivered!")
        del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("no_"):
        parts = data.split("_")
        order_id = parts[1]
        user_cid = int(parts[2])
        
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Admin only!")
            return
        
        bot.send_message(user_cid, """
❌ *PAYMENT NOT VERIFIED*
━━━━━━━━━━━━━━━━━━━━━━

We couldn't verify your payment.

📞 *Contact support for assistance*
@ReddyHack

🔄 *Try again from main menu*
""", parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected")
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
    
    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.edit_message_caption(cid, call.message.id, caption="❌ ORDER CANCELLED", reply_markup=None)
        bot.send_message(cid, "🔄 *Start fresh from main menu*", parse_mode="Markdown", reply_markup=main_menu())

def expire(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid, """
⌛ *ORDER EXPIRED*
━━━━━━━━━━━━━━━━━━━━━━

Time limit exceeded (15 minutes).

🔄 *Please start a new purchase*
👇 *Tap below to begin*
""", parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API
# ============================================================

@app.route('/')
def home():
    total = sum(len(db["keys"].get(p, {}).get(d, [])) for p in db["keys"] for d in ["day","week","month"])
    return jsonify({"status": "online", "keys": total, "version": "premium"})

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
    print("=" * 50)
    print("👑 REDDY PREMIUM BOT - ULTRA PREMIUM")
    print("=" * 50)
    print("✅ Stickers: ENABLED")
    print("✅ Premium UI: ENABLED")
    print("✅ Stock Display: ENABLED")
    print("=" * 50)
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - UPGRADED VERSION
Clean, Professional, Feature-Rich
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = os.environ.get("ADMIN_ID", "1648621649")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "reddy_secure_2024")
SUPPORT_USERNAME = "@ReddyHack"
CHANNEL_LINK = "https://t.me/ReddyPremium"
UPI_ID = "q542401897@ybl"

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}
user_states = {}  # For support flow

PRODUCTS = {
    "deadeye": {"name": "Deadeye",  "emoji": "🎯"},
    "vision":  {"name": "Vision",   "emoji": "👁️"},
    "rage":    {"name": "Rage",     "emoji": "⚡"},
    "winios":  {"name": "WinIOS",   "emoji": "💻"},
    "kingios": {"name": "KingIOS",  "emoji": "👑"},
}

PRICES = {
    "deadeye": {"day": 149, "week": 699, "month": 1299},
    "vision":  {"day": 199, "week": 699, "month": 2200},
    "rage":    {"day": 149, "week": 699, "month": 1299},
    "winios":  {"day": 149, "week": 599, "month":  999},
    "kingios": {"day": 199, "week": 699, "month": 2200},
}

PREFIX = {
    "deadeye": "DEAD",
    "vision":  "VIS",
    "rage":    "RAGE",
    "winios":  "WIN",
    "kingios": "KING",
}

DURATION_LABEL = {
    "day":   "1 Day",
    "week":  "7 Days",
    "month": "30 Days",
}

db = {
    "users":  {},
    "orders": [],
    "keys":   {p: {"day": [], "week": [], "month": []} for p in PRODUCTS},
}

# ============================================================
# HELPERS
# ============================================================

def get_stock(product, duration):
    return len(db["keys"].get(product, {}).get(duration, []))

def pop_key(product, duration):
    pool = db["keys"].get(product, {}).get(duration, [])
    return pool.pop(0) if pool else None

def save_user_key(user_id, username, product, duration, key):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {"username": username, "keys": [], "joined": now_str()}
    db["users"][uid]["keys"].append({
        "product": product, "duration": duration,
        "key": key, "date": now_str()
    })

def now_str():
    return datetime.datetime.now().strftime("%d %b %Y %I:%M %p")

def expiry_str(duration):
    days = {"day": 1, "week": 7, "month": 30}[duration]
    exp = datetime.datetime.now() + datetime.timedelta(days=days)
    return exp.strftime("%d %b %Y")

def make_qr(amount, order_id):
    upi = f"upi://pay?pa={UPI_ID}&pn=Reddy+Premium&am={amount}&tn={order_id}&cu=INR"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(upi)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def check_low_stock():
    """Alert admin when any product stock drops to 3 or below."""
    alerts = []
    for p, pdata in PRODUCTS.items():
        for d in ["day", "week", "month"]:
            count = get_stock(p, d)
            if 0 < count <= 3:
                alerts.append(f"⚠️ {pdata['emoji']} {pdata['name']} {DURATION_LABEL[d]}: only *{count}* left!")
    if alerts:
        msg = "🔔 *Low Stock Alert*\n\n" + "\n".join(alerts) + "\n\nAdd keys via admin panel."
        try:
            bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
        except:
            pass

def today_stats():
    today = datetime.datetime.now().strftime("%d %b %Y")
    today_orders = [o for o in db["orders"] if today in o.get("date", "")]
    revenue = sum(o.get("amount", 0) for o in today_orders)
    return len(today_orders), revenue

# ============================================================
# KEYBOARDS
# ============================================================

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 Buy Key",   callback_data="buy"),
        InlineKeyboardButton("🔑 My Keys",   callback_data="mykeys"),
        InlineKeyboardButton("📦 Stock",     callback_data="stock"),
        InlineKeyboardButton("🆘 Support",   callback_data="support"),
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
    for dur, label in DURATION_LABEL.items():
        stock = get_stock(product, dur)
        price = prices[dur]
        status = " ❌" if stock == 0 else f" [{stock} left]"
        kb.add(InlineKeyboardButton(
            f"📅 {label} — ₹{price}{status}",
            callback_data=f"plan_{product}_{dur}"
        ))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="buy"))
    return kb

def pay_kb(order_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ I have Paid", callback_data=f"paid_{order_id}"),
        InlineKeyboardButton("❌ Cancel",       callback_data=f"cancel_{order_id}"),
    )
    return kb

def admin_order_kb(order_id, user_cid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Approve & Send Key", callback_data=f"ok_{order_id}_{user_cid}"))
    kb.add(InlineKeyboardButton("❌ Reject",              callback_data=f"no_{order_id}_{user_cid}"))
    return kb

# ============================================================
# /start
# ============================================================

@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "username": msg.from_user.username or "User",
            "keys": [], "joined": now_str()
        }
    text = (
        f"👋 Welcome, *{msg.from_user.first_name}*!\n\n"
        f"🏪 *Reddy Premium* — Trusted License Shop\n\n"
        f"✅ 100% Genuine Keys\n"
        f"⚡ Instant Delivery After Verification\n"
        f"🛡️ Safe UPI Payment\n"
        f"🕐 Support: {SUPPORT_USERNAME}\n\n"
        f"👇 Choose an option below:"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

# ============================================================
# ADMIN COMMANDS
# ============================================================

@bot.message_handler(commands=['stats'])
def admin_stats(msg):
    if str(msg.from_user.id) != ADMIN_ID:
        return
    total_keys = sum(get_stock(p, d) for p in PRODUCTS for d in ["day","week","month"])
    today_count, today_rev = today_stats()
    total_rev = sum(o.get("amount", 0) for o in db["orders"])
    text = (
        f"📊 *Admin Dashboard*\n\n"
        f"👥 Total Users: *{len(db['users'])}*\n"
        f"📦 Keys in Stock: *{total_keys}*\n"
        f"🧾 Total Orders: *{len(db['orders'])}*\n"
        f"💰 Total Revenue: *₹{total_rev}*\n\n"
        f"📅 *Today*\n"
        f"   Orders: *{today_count}*\n"
        f"   Revenue: *₹{today_rev}*\n\n"
        f"📦 *Stock Breakdown*\n"
    )
    for p, pdata in PRODUCTS.items():
        d = get_stock(p, "day")
        w = get_stock(p, "week")
        m = get_stock(p, "month")
        text += f"   {pdata['emoji']} {pdata['name']}: {d}D | {w}W | {m}M\n"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def admin_broadcast(msg):
    if str(msg.from_user.id) != ADMIN_ID:
        return
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        bot.send_message(msg.chat.id, "Usage: /broadcast Your message here")
        return
    broadcast_text = parts[1]
    sent, failed = 0, 0
    for uid in db["users"]:
        try:
            bot.send_message(int(uid),
                f"📢 *Message from Reddy Premium*\n\n{broadcast_text}",
                parse_mode="Markdown")
            sent += 1
        except:
            failed += 1
    bot.send_message(msg.chat.id,
        f"✅ Broadcast done!\nSent: {sent} | Failed: {failed}",
        parse_mode="Markdown")

@bot.message_handler(commands=['addkeys'])
def admin_add_keys(msg):
    if str(msg.from_user.id) != ADMIN_ID:
        return
    # Format: /addkeys deadeye day KEY1 KEY2 KEY3
    parts = msg.text.split()
    if len(parts) < 4:
        bot.send_message(msg.chat.id,
            "Usage: `/addkeys <product> <day|week|month> KEY1 KEY2 ...`",
            parse_mode="Markdown")
        return
    product, duration = parts[1], parts[2]
    keys = parts[3:]
    if product not in PRODUCTS or duration not in ["day","week","month"]:
        bot.send_message(msg.chat.id, "❌ Invalid product or duration.")
        return
    db["keys"][product][duration].extend(keys)
    bot.send_message(msg.chat.id,
        f"✅ Added *{len(keys)}* keys to *{PRODUCTS[product]['name']}* ({duration})\n"
        f"Total now: *{get_stock(product, duration)}*",
        parse_mode="Markdown")

# ============================================================
# SUPPORT FLOW
# ============================================================

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)] == "awaiting_support")
def receive_support_msg(msg):
    uid = str(msg.from_user.id)
    user_states.pop(uid, None)
    uname = msg.from_user.username or "No username"
    admin_msg = (
        f"🆘 *Support Request*\n\n"
        f"👤 @{uname} (ID: {uid})\n"
        f"📝 {msg.text}\n\n"
        f"Reply via Telegram."
    )
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except:
        pass
    bot.send_message(msg.chat.id,
        "✅ *Support request sent!*\n\nOur team will contact you soon.\n"
        f"You can also reach us at {SUPPORT_USERNAME}",
        parse_mode="Markdown", reply_markup=main_menu())

# ============================================================
# CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(func=lambda c: True)
def handle(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    uname = call.from_user.username or "User"
    data = call.data

    # Back to main
    if data == "back":
        bot.edit_message_text(
            "👇 *Main Menu* — Choose an option:",
            cid, call.message.id,
            parse_mode="Markdown", reply_markup=main_menu())

    elif data == "buy":
        bot.edit_message_text(
            "🛒 *Select a Product*\n\nAll keys are genuine & verified.",
            cid, call.message.id,
            parse_mode="Markdown", reply_markup=products_kb())

    elif data == "mykeys":
        uid_str = str(uid)
        keys = db["users"].get(uid_str, {}).get("keys", [])
        if not keys:
            text = (
                "🔑 *My Keys*\n\n"
                "You haven't purchased any keys yet.\n\n"
                "Tap *Buy Key* to get started! 👇"
            )
        else:
            text = "🔑 *Your Recent Keys*\n\n"
            for k in keys[-5:]:
                text += (
                    f"📦 {k['product']} — {DURATION_LABEL.get(k['duration'], k['duration'])}\n"
                    f"🔑 `{k['key']}`\n"
                    f"📅 {k['date']}\n\n"
                )
        bot.edit_message_text(text, cid, call.message.id,
            parse_mode="Markdown", reply_markup=main_menu())

    elif data == "stock":
        text = "📦 *Current Stock*\n\n"
        for key, p in PRODUCTS.items():
            day   = get_stock(key, "day")
            week  = get_stock(key, "week")
            month = get_stock(key, "month")
            total = day + week + month
            if total > 0:
                text += f"{p['emoji']} *{p['name']}*\n   1D: {day} | 7D: {week} | 30D: {month}\n\n"
            else:
                text += f"{p['emoji']} *{p['name']}* — Out of Stock ❌\n\n"
        bot.edit_message_text(text, cid, call.message.id,
            parse_mode="Markdown", reply_markup=main_menu())

    elif data == "support":
        user_states[str(uid)] = "awaiting_support"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("💬 Chat on Telegram", url=f"https://t.me/ReddyHack"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back"))
        bot.edit_message_text(
            "🆘 *Support*\n\n"
            "Type your issue below (include Order ID if any)\n"
            "and we'll get back to you.\n\n"
            "OR tap below to contact directly:",
            cid, call.message.id,
            parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("prod_"):
        product = data.split("_")[1]
        p = PRODUCTS[product]
        total = sum(get_stock(product, d) for d in ["day","week","month"])
        availability = "✅ Available" if total > 0 else "❌ Out of Stock"
        text = (
            f"{p['emoji']} *{p['name']}*\n\n"
            f"Status: {availability}\n\n"
            f"Select your plan:"
        )
        bot.edit_message_text(text, cid, call.message.id,
            parse_mode="Markdown", reply_markup=plans_kb(product))

    elif data.startswith("plan_"):
        _, product, duration = data.split("_")
        if get_stock(product, duration) == 0:
            bot.answer_callback_query(call.id, "❌ Out of stock! Choose another plan.", show_alert=True)
            return
        amount   = PRICES[product][duration]
        order_id = f"RP{int(time.time())}{random.randint(10,99)}"
        pending_orders[order_id] = {
            "user_id": uid, "username": uname,
            "product": product, "duration": duration,
            "amount": amount, "chat_id": cid,
            "created": time.time()
        }
        qr = make_qr(amount, order_id)
        caption = (
            f"🧾 *Order Confirmation*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Product: *{PRODUCTS[product]['name']}*\n"
            f"⏱ Duration: *{DURATION_LABEL[duration]}*\n"
            f"💰 Amount: *₹{amount}*\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📲 Pay via UPI:\n"
            f"`{UPI_ID}`\n\n"
            f"⏳ *This order expires in 15 minutes*\n\n"
            f"After payment, tap ✅ *I have Paid*"
        )
        bot.delete_message(cid, call.message.id)
        bot.send_photo(cid, qr, caption=caption,
            parse_mode="Markdown", reply_markup=pay_kb(order_id))
        threading.Timer(900, lambda: expire(order_id, cid)).start()

    elif data.startswith("paid_"):
        order_id = data.split("_")[1]
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "⏱ Order expired! Please start again.", show_alert=True)
            return
        o = pending_orders[order_id]
        bot.answer_callback_query(call.id, "✅ Notifying admin. Please wait...")
        admin_msg = (
            f"💰 *Payment Claim*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User: @{uname} (ID: {uid})\n"
            f"📦 {PRODUCTS[o['product']]['name']} — {DURATION_LABEL[o['duration']]}\n"
            f"💰 ₹{o['amount']}\n"
            f"🆔 {order_id}\n"
            f"🕐 {now_str()}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Verify payment & approve below:"
        )
        bot.send_message(ADMIN_ID, admin_msg,
            parse_mode="Markdown", reply_markup=admin_order_kb(order_id, cid))
        # Edit user message
        bot.edit_message_caption(
            caption=(
                "⏳ *Verification in progress...*\n\n"
                f"Order ID: `{order_id}`\n\n"
                "Admin will verify your payment shortly.\n"
                f"Need help? Contact {SUPPORT_USERNAME}"
            ),
            chat_id=cid, message_id=call.message.id,
            parse_mode="Markdown")

    elif data.startswith("ok_"):
        _, order_id, user_cid = data.split("_")
        user_cid = int(user_cid)
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Admin only!", show_alert=True)
            return
        if order_id not in pending_orders:
            bot.answer_callback_query(call.id, "Order not found or expired.", show_alert=True)
            return
        o = pending_orders[order_id]
        if get_stock(o['product'], o['duration']) == 0:
            bot.answer_callback_query(call.id, "❌ No stock! Add keys first.", show_alert=True)
            return
        key = pop_key(o['product'], o['duration'])
        if not key:
            bot.answer_callback_query(call.id, "Error fetching key.", show_alert=True)
            return
        save_user_key(o['user_id'], o['username'], PRODUCTS[o['product']]['name'], o['duration'], key)
        db["orders"].append({
            "username": o['username'], "product": PRODUCTS[o['product']]['name'],
            "duration": o['duration'], "amount": o['amount'],
            "key": key, "date": now_str()
        })
        exp = expiry_str(o['duration'])
        delivery_msg = (
            f"✅ *Payment Verified — Key Delivered!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Product: *{PRODUCTS[o['product']]['name']}*\n"
            f"⏱ Duration: *{DURATION_LABEL[o['duration']]}*\n"
            f"💰 Amount: ₹{o['amount']}\n"
            f"📅 Expires: *{exp}*\n"
            f"🆔 Order: `{order_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 *Your License Key:*\n"
            f"`{key}`\n\n"
            f"📋 Copy the key and activate it.\n"
            f"Need help? {SUPPORT_USERNAME}\n\n"
            f"Thank you for choosing *Reddy Premium!* 👑"
        )
        bot.send_message(user_cid, delivery_msg,
            parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "✅ Key sent to user!")
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
        del pending_orders[order_id]
        check_low_stock()

    elif data.startswith("no_"):
        _, order_id, user_cid = data.split("_")
        user_cid = int(user_cid)
        if str(uid) != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Admin only!", show_alert=True)
            return
        bot.send_message(user_cid,
            f"❌ *Payment Not Verified*\n\n"
            f"Order ID: `{order_id}`\n\n"
            f"Possible reasons:\n"
            f"• Payment amount incorrect\n"
            f"• UPI ID mismatch\n"
            f"• Screenshot not clear\n\n"
            f"Please try again or contact {SUPPORT_USERNAME}",
            parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected.")
        bot.edit_message_reply_markup(cid, call.message.id, reply_markup=None)
        if order_id in pending_orders:
            del pending_orders[order_id]

    elif data.startswith("cancel_"):
        order_id = data.split("_")[1]
        if order_id in pending_orders:
            del pending_orders[order_id]
        bot.delete_message(cid, call.message.id)
        bot.send_message(cid,
            "❌ *Order Cancelled*\n\nYou can start a new order anytime.",
            parse_mode="Markdown", reply_markup=main_menu())

def expire(order_id, cid):
    if order_id in pending_orders:
        del pending_orders[order_id]
        try:
            bot.send_message(cid,
                "⌛ *Order Expired*\n\nYour 15-minute payment window has passed.\n"
                "Please start a new order.",
                parse_mode="Markdown", reply_markup=main_menu())
        except:
            pass

# ============================================================
# FLASK API
# ============================================================

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": "Reddy Premium Bot"})

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin_panel.html')

@app.route('/api/dashboard')
def dashboard():
    total_keys = sum(get_stock(p, d) for p in PRODUCTS for d in ["day","week","month"])
    tc, tr = today_stats()
    return jsonify({
        "total_keys": total_keys,
        "total_orders": len(db["orders"]),
        "total_users": len(db["users"]),
        "total_revenue": sum(o.get("amount", 0) for o in db["orders"]),
        "today_orders": tc,
        "today_revenue": tr,
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
    db["keys"].setdefault(p, {"day":[],"week":[],"month":[]})[d].extend(ks)
    check_low_stock()
    return jsonify({"ok": True, "total": get_stock(p, d)})

@app.route('/api/keys/generate', methods=['POST'])
def gen_keys():
    data = request.json
    p, d, c = data['product'], data['duration'], data['count']
    pre = PREFIX.get(p, "KEY")
    def g():
        r = lambda: ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789', k=4))
        return f"{pre}-{r()}-{r()}-{r()}"
    new = [g() for _ in range(c)]
    db["keys"].setdefault(p, {"day":[],"week":[],"month":[]})[d].extend(new)
    return jsonify({"ok": True, "generated": len(new)})

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
    if request.json.get('password') == ADMIN_PASSWORD:
        return jsonify({"token": "ok"})
    return jsonify({"error": "Wrong password"}), 401

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(
            request.get_data().decode('UTF-8'))])
        return '', 200
    return '', 403

if __name__ == "__main__":
    print("=" * 40)
    print("👑 REDDY PREMIUM BOT STARTING...")
    print("=" * 40)
    bot.remove_webhook()
    url = os.environ.get('RENDER_EXTERNAL_URL', 'https://reddy-bot.onrender.com')
    bot.set_webhook(f"{url}/webhook")
    app.run(host='0.0.0.0', port=8080)

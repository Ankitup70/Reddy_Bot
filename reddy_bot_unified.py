#!/usr/bin/env python3
"""
👑 REDDY PREMIUM BOT - WITH MONGODB (PERSISTENT STORAGE)
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

# MongoDB Connection (REPLACE WITH YOUR OWN)
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

# Initialize default data if empty
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

# Stickers & Prices (static)
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

# Helpers using MongoDB
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

def add_keys(product, duration, key_list):
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

# Flask app and bot setup (rest unchanged from your working version, just replace db helpers)
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)
pending_orders = {}

# ... (rest of your existing bot code – keep same keyboards and handlers, 
# but ensure all db calls use the new functions above)

# Since the full code is long, I'll provide the critical changes.
# You should replace the entire file with the complete code available in the next message.

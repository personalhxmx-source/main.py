import os
import random
import string
import datetime
import asyncio
import pyotp
import pandas as pd
import openpyxl
import pymongo
from flask import Flask
from threading import Thread
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, 
    ConversationHandler, filters, CallbackQueryHandler
)

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = "9288377749:AAHrbEM2cVkC3EXZncQVS2T4P2yFqN2ZkMo"
ADMIN_ID = 8279212458
MIN_WITHDRAW = 20.0
WITHDRAW_FEE = 5.0

# 🌐 MongoDB Connection
MONGO_URI = "mongodb+srv://hasansumaiyax_db_user:dZHnDk1nbSzlGaxo@cluster0.kjouetx.mongodb.net/"
client = pymongo.MongoClient(MONGO_URI)
db_mongo = client["insta_bot_db"]

users_col = db_mongo["users"]
tasks_col = db_mongo["tasks"]
withdraws_col = db_mongo["withdraws"]
config_col = db_mongo["config"]
methods_col = db_mongo["methods"]
# -----------------

def get_config():
    conf = config_col.find_one({"id": "settings"})
    if not conf:
        default_conf = {
            "id": "settings",
            "insta_rates": [5.0, 6.0, 7.0],
            "fb_rates": [5.0, 6.0, 7.0, 8.0],
            "insta_pass": "InstaPass123!",
            "fb_pass": "FbPass123!",
            "support_link": "https://t.me/telegram",
            "required_channel": "@your_official_channel",
            "insta_video": "",
            "fb_video": "",
            "bkash_video": "",
            "nagad_video": "",
            "roket_video": "",
            "insta_task_active": True,
            "fb_task_active": True
        }
        config_col.insert_one(default_conf)
        return default_conf
    
    updates = {}
    if "fb_rates" not in conf: updates["fb_rates"] = [5.0, 6.0, 7.0, 8.0]
    if "fb_pass" not in conf: updates["fb_pass"] = "FbPass123!"
    if "insta_rates" not in conf and "rates" in conf: updates["insta_rates"] = conf["rates"]
    if "insta_pass" not in conf and "default_pass" in conf: updates["insta_pass"] = conf["default_pass"]
    if "support_link" not in conf: updates["support_link"] = "https://t.me/telegram"
    if "required_channel" not in conf: updates["required_channel"] = "@your_official_channel"
    if "insta_video" not in conf: updates["insta_video"] = ""
    if "fb_video" not in conf: updates["fb_video"] = ""
    if "bkash_video" not in conf: updates["bkash_video"] = ""
    if "nagad_video" not in conf: updates["nagad_video"] = ""
    if "roket_video" not in conf: updates["roket_video"] = ""
    if "insta_task_active" not in conf: updates["insta_task_active"] = True
    if "fb_task_active" not in conf: updates["fb_task_active"] = True

    if updates:
        config_col.update_one({"id": "settings"}, {"$set": updates})
        conf.update(updates)

    return conf

def get_custom_date():
    now = datetime.datetime.now()
    if now.hour >= 19:
        target_date = now + datetime.timedelta(days=1)
    else:
        target_date = now
    return target_date.strftime("%d-%m-%Y")

def get_user(user_id, referred_by=None):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user_data = {
            "user_id": user_id,
            "balance": 0.0, 
            "pending_withdraw": 0.0, 
            "completed": 0, 
            "review": 0,
            "total_earned": 0.0,
            "referred_by": referred_by,
            "total_refers": 0
        }
        users_col.insert_one(user_data)
        if referred_by:
            users_col.update_one({"user_id": referred_by}, {"$inc": {"total_refers": 1}})
        return user_data
    return user

def generate_random_username():
    prefix = "insta_" + "".join(random.choices(string.ascii_lowercase, k=4))
    digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}_{digits}"

def generate_random_fb_name():
    first_names = ["Tanvir", "Sabbir", "Arif", "Mehedi", "Nayan", "Rakib", "Shakil", "Mahfuz"]
    last_names = ["Hossain", "Ahmed", "Islam", "Rahman", "Khan", "Chowdhury", "Sheikh"]
    return random.choice(first_names), random.choice(last_names)

# 🔄 Conversation States
_states_list = [
    "WORK_SELECT_PLATFORM", "WORK_SELECT_TYPE", "WORK_SELECT_RATE", "ENTERING_2FA", "TASK_CONFIRM",
    "FB_SELECT_TYPE", "FB_SELECT_COOKIE_TYPE", "FB_SELECT_RATE", "FB_ENTER_UID", "FB_ENTER_COOKIES", "FB_TASK_CONFIRM",
    "ADMIN_SET_INSTA_PASS", "ADMIN_SET_FB_PASS", "ADMIN_SET_INSTA_RATE", "ADMIN_SET_FB_RATE",
    "ADMIN_SELECT_FILE_PLATFORM", "ADMIN_GET_DATE_FILE", "ADMIN_SELECT_REPORT_PLATFORM", "ADMIN_GET_DATE_REPORT", "ADMIN_UPLOAD_REPORT",
    "WITHDRAW_METHOD", "WITHDRAW_NUMBER", "WITHDRAW_AMOUNT",
    "ADMIN_SET_SUPPORT", "ADMIN_SET_CHANNEL", 
    "ADMIN_VIDEO_MENU", "ADMIN_SET_INSTA_VID", "ADMIN_SET_FB_VID", "ADMIN_SET_BKASH_VID", "ADMIN_SET_NAGAD_VID", "ADMIN_SET_ROKET_VID",
    "METHOD_SELECT_PLATFORM", "METHOD_AVAILABLE_MENU", "METHOD_SEND_VIDEO", "ADMIN_METHOD_MENU", "ADMIN_ADD_METHOD_PLATFORM", "ADMIN_ADD_METHOD_NAME", "ADMIN_ADD_METHOD_FILE", 
    "ADMIN_DEL_METHOD_PLATFORM", "ADMIN_DEL_METHOD_SELECT",
    "ADMIN_BROADCAST_MSG", "ADMIN_TASK_ON_OFF_MENU",
    "ADMIN_USER_MGMT_INPUT", "ADMIN_USER_EDIT_CHOICE", "ADMIN_USER_EDIT_VALUE"
]
globals().update({name: idx for idx, name in enumerate(_states_list)})

# ----------------- CLEAN & BOLD KEYBOARDS -----------------
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🎯 কাজ শুরু", "💰 ব্যালেন্স"],
        ["💸 টাকা উত্তোলন", "🎁 রেফারেল"],
        ["🎧 সাপোর্ট", "📚 মেথড"]
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["⚙️ কাস্টমাইজ", "💸 উইথড্র কন্ট্রোল"],
        ["📁 টাস্ক সেন্টার", "👥 ইউজার কন্ট্রোল"],
        ["🗄️ ডাটাবেজ", "👥 মোট ইউজার"],
        ["📢 ব্রডকাস্ট", "🔙 মূল মেনু"]
    ], resize_keyboard=True)

def admin_custom_keyboard():
    return ReplyKeyboardMarkup([
        ["🔌 কাজ অন/অফ", "📢 চ্যানেল সেট"],
        ["🎬 ভিডিও ম্যানেজমেন্ট"],
        ["🔑 🔴 Instagram পাসওয়ার্ড", "🔑 🔵 Facebook পাসওয়ার্ড"],
        ["💵 🔴 Instagram রেট", "💵 🔵 Facebook রেট"],
        ["🎧 সাপোর্ট লিংক", "📁 মেথড কন্ট্রোল"],
        ["🔙 এডমিন মেনু"]
    ], resize_keyboard=True)

def admin_video_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["🎬 🔴 Instagram ভিডিও", "🎬 🔵 Facebook ভিডিও"],
        ["🎬 BKASH ভিডিও", "🎬 NAGAD ভিডিও", "🎬 ROKET ভিডিও"],
        ["🗑️ ভিডিও ডিলিট", "🔙 কাস্টমাইজ মেনু"]
    ], resize_keyboard=True)

def admin_all_tasks_keyboard():
    return ReplyKeyboardMarkup([
        ["📥 ফাইল ডাউনলোড", "📤 রিপোর্ট জমা"],
        ["🔙 এডমিন মেনু"]
    ], resize_keyboard=True)

def platform_choice_keyboard():
    return ReplyKeyboardMarkup([
        ["🔴 Instagram", "🔵 Facebook"],
        ["❌ বাতিল"]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([["❌ বাতিল"]], resize_keyboard=True)

# ----------------- FORCE JOIN SYSTEM -----------------
async def check_joined_channel(user_id, context: ContextTypes.DEFAULT_TYPE):
    conf = get_config()
    channel = conf.get("required_channel", "@your_official_channel")
    if not channel or channel == "@your_official_channel":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

async def force_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conf = get_config()
    channel = conf.get("required_channel", "@your_official_channel")
    if channel == "@your_official_channel" or not channel:
        return True 
    
    is_joined = await check_joined_channel(user_id, context)
    if not is_joined:
        join_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{channel.replace('@', '')}")],
            [InlineKeyboardButton("🔄 জয়েন চেক করুন", callback_data="check_join")]
        ])
        if update.message:
            await update.message.reply_text(
                "**⚠️ সতর্কবার্তা! বটটি ব্যবহার করতে হলে অবশ্যই আমাদের অফিশিয়াল চ্যানেলে জয়েন করতে হবে।**\n\n"
                "**চ্যানেলে জয়েন করার পর নিচের '🔄 জয়েন চেক করুন' বাটনে চাপ দিন:**",
                reply_markup=join_kb,
                parse_mode="Markdown"
            )
        return False
    return True

async def inline_join_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
    except Exception:
        pass

    if query.data == "check_join":
        is_joined = await check_joined_channel(user_id, context)
        if is_joined:
            try:
                await query.message.edit_text("**✅ ধন্যবাদ! চ্যানেল জয়েন নিশ্চিত করা হয়েছে।**", parse_mode="Markdown")
            except Exception:
                pass
            
            msg = (
                "**✨ স্বাগতম! ছোট ছোট টাস্ক সম্পন্ন করে ঘরে বসে নিশ্চিত আয় করুন – সহজ, নিরাপদ ও দ্রুত পেমেন্ট 💸**\n\n"
                "**👇 নিচের মেনু থেকে আপনার পছন্দসই অপশনটি বেছে নিন:**"
            )
            await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=main_keyboard(), parse_mode="Markdown")
        else:
            try:
                await query.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।", show_alert=True)
            except Exception:
                pass

# ----------------- CANCEL & SMART BACK HANDLERS -----------------
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("**❌ সফলভাবে বাতিল করা হয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def smart_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data.clear()
    
    if text == "🔙 এডমিন মেনু":
        await update.message.reply_text("**🛡️ এডমিন কন্ট্রোল প্যানেল:**", reply_markup=admin_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    elif text == "🔙 কাস্টমাইজ মেনু":
        await update.message.reply_text("**⚙️ কাস্টমাইজ প্যানেল:**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    elif text == "🔙 মূল মেনু":
        await update.message.reply_text("**🏠 আপনি মূল ড্যাশবোর্ডে ফিরে এসেছেন।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    else:
        await update.message.reply_text("**🔙 এক ধাপ পেছনে ফিরে আসা হয়েছে।**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

# ----------------- USER COMMANDS & HANDLERS -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context):
        return

    context.user_data.clear()
    user_id = update.effective_user.id
    referred_by = None
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])
        if ref_id != user_id: referred_by = ref_id
    
    get_user(user_id, referred_by)
    
    msg = (
        "**✨ স্বাগতম! ছোট ছোট টাস্ক সম্পন্ন করে ঘরে বসে নিশ্চিত আয় করুন – সহজ, নিরাপদ ও দ্রুত পেমেন্ট 💸**\n\n"
        "**👇 নিচের মেনু থেকে আপনার পছন্দসই অপশনটি বেছে নিন:**"
    )
    await update.message.reply_text(msg, reply_markup=main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    u = get_user(update.effective_user.id)
    msg = (
        "**💎 ব্যালেন্স ও ওয়ালেট ড্যাশবোর্ড**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 **বর্তমান ব্যালেন্স:** `{u['balance']:.2f}` টাকা\n"
        f"⏳ **পেন্ডিং উইথড্র:** `{u['pending_withdraw']:.2f}` টাকা\n"
        f"✅ **সফল টাস্ক:** `{u['completed']}` টি\n"
        f"🔍 **রিভিউ টাস্ক:** `{u['review']}` টি\n"
        f"🏆 **মোট আয়:** `{u['total_earned']:.2f}` টাকা\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def refer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return
    user_id = update.effective_user.id
    u = get_user(user_id)
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    msg = (
        "**⚡ স্মার্ট রেফারেল ও ইনভাইট নেটওয়ার্ক**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **রেফারকৃত মেম্বার:** `{u['total_refers']}` জন\n"
        "🎁 আপনার রেফারকৃত ব্যক্তি পেমেন্ট তুললে আজীবন ৫ টাকা কমিশন পাবেন!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 **আপনার ইনভাইট লিংক:**\n"
        f"`{ref_link}`\n\n"
        "**🚀 বন্ধুদের সাথে শেয়ার করে ইনকাম বাড়ান!**"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conf = get_config()
    admin_url = conf.get("support_link", "https://t.me/telegram").strip()
    if not admin_url.startswith("http://") and not admin_url.startswith("https://"):
        admin_url = f"https://t.me/{admin_url.replace('@', '')}"
    
    channel = conf.get("required_channel", "@your_official_channel")
    channel_url = f"https://t.me/{channel.replace('@', '')}" if channel else "https://t.me/telegram"

    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 এডমিন লাইভ সাপোর্ট", url=admin_url)],
        [InlineKeyboardButton("📢 অফিশিয়াল চ্যানেল", url=channel_url)]
    ])
    
    msg = (
        "**🎧 অফিশিয়াল সাপোর্ট সেন্টার ও চ্যানেল**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**যেকোনো প্রয়োজনে নিচের বাটনগুলো ব্যবহার করুন:**"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_kb)

# --- USER METHOD SYSTEM (📚 মেথড) ---
async def method_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return ConversationHandler.END
    await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
    return METHOD_SELECT_PLATFORM

async def method_platform_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    platform = None
    if "Instagram" in text:
        platform = "Instagram"
    elif "Facebook" in text:
        platform = "Facebook"
    else:
        await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", parse_mode="Markdown", reply_markup=platform_choice_keyboard())
        return METHOD_SELECT_PLATFORM

    context.user_data["user_method_platform"] = platform
    btn_text = "IG Available Method" if platform == "Instagram" else "FB Available Method"
    kb = ReplyKeyboardMarkup([[btn_text], ["❌ বাতিল"]], resize_keyboard=True)
    await update.message.reply_text("**🔷 মেথড লিস্ট সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
    return METHOD_AVAILABLE_MENU

async def method_show_titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Available Method" not in text:
        await update.message.reply_text("**🔷 সিলেক্ট করুন:**", parse_mode="Markdown")
        return METHOD_AVAILABLE_MENU

    platform = context.user_data.get("user_method_platform", "Instagram")
    methods = list(methods_col.find({"platform": platform}))
    
    if not methods:
        p_name = "🔴 Instagram" if platform == "Instagram" else "🔵 Facebook"
        await update.message.reply_text(f"**⚠️ {p_name}-এর জন্য কোনো মেথড নেই।**", reply_markup=main_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

    keyboard_rows = []
    for m in methods:
        keyboard_rows.append([m['name']])
    keyboard_rows.append(["❌ বাতিল"])
    
    kb = ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True)
    await update.message.reply_text("**🔷 মেথড সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
    return METHOD_SEND_VIDEO

async def method_send_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    platform = context.user_data.get("user_method_platform", "Instagram")
    
    method_doc = methods_col.find_one({"platform": platform, "name": title})
    if not method_doc:
        await update.message.reply_text("**❌ এই নামের কোনো মেথড নেই।**", parse_mode="Markdown")
        return METHOD_SEND_VIDEO

    file_id = method_doc["file_id"]
    try:
        await update.message.reply_video(video=file_id, caption=f"**🎬 মেথড টাইটেল:** {title}", parse_mode="Markdown", reply_markup=main_keyboard())
    except Exception:
        await update.message.reply_text(f"**🎬 মেথড: {title}**\nফাইল আইডি: `{file_id}`", parse_mode="Markdown", reply_markup=main_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

# ----------------- WORK FLOW SYSTEM (🎯 কাজ শুরু) -----------------
async def work_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return ConversationHandler.END
    await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
    return WORK_SELECT_PLATFORM

async def work_platform_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conf = get_config()

    if "Instagram" in text:
        if not conf.get("insta_task_active", True):
            await update.message.reply_text("**⚠️ 🔴 Instagram কাজ সাময়িকভাবে বন্ধ রয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
            return ConversationHandler.END
            
        kb = ReplyKeyboardMarkup([["🔑 INSTA 2FA"], ["▶️ কাজের ভিডিও"], ["❌ বাতিল"]], resize_keyboard=True)
        await update.message.reply_text("**🔷 অপশন সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
        return WORK_SELECT_TYPE

    elif "Facebook" in text:
        if not conf.get("fb_task_active", True):
            await update.message.reply_text("**⚠️ 🔵 Facebook কাজ সাময়িকভাবে বন্ধ রয়েছে।**", reply_markup=main_keyboard(), parse_mode="Markdown")
            return ConversationHandler.END

        kb = ReplyKeyboardMarkup([["📱 Number/Anymail"], ["▶️ কাজের ভিডিও"], ["❌ বাতিল"]], resize_keyboard=True)
        await update.message.reply_text("**🔷 অপশন সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
        return FB_SELECT_TYPE
    
    await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", parse_mode="Markdown", reply_markup=platform_choice_keyboard())
    return WORK_SELECT_PLATFORM

async def work_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "▶️ কাজের ভিডিও":
        conf = get_config()
        vid = conf.get("insta_video", "")
        if vid:
            try:
                await update.message.reply_video(video=vid, caption="**🎬 🔴 Instagram কাজের ভিডিও টিউটোরিয়াল**", parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("**⚠️ এখনো ভিডিও সেট করা হয়নি।**", parse_mode="Markdown")
        return WORK_SELECT_TYPE

    if text == "🔑 INSTA 2FA":
        conf = get_config()
        rate_buttons = [[f"💰 {r} টাকা"] for r in conf["insta_rates"]]
        rate_buttons.append(["❌ বাতিল"])
        kb = ReplyKeyboardMarkup(rate_buttons, resize_keyboard=True)
        await update.message.reply_text("**🔷 রেট সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
        return WORK_SELECT_RATE
    await update.message.reply_text("**❌ অকার্যকর অপশন!**", parse_mode="Markdown")
    return WORK_SELECT_TYPE

async def work_rate_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        selected_rate = float(update.message.text.replace("💰", "").replace("টাকা", "").strip())
    except ValueError:
        await update.message.reply_text("**❌ সঠিক রেট সিলেক্ট করুন।**", parse_mode="Markdown")
        return WORK_SELECT_RATE

    conf = get_config()
    generated_user = generate_random_username()
    password = conf["insta_pass"]
    
    context.user_data["task_platform"] = "Instagram"
    context.user_data["task_rate"] = selected_rate
    context.user_data["task_insta_user"] = generated_user
    context.user_data["task_pass"] = password
    
    msg = (
        "**✨ নতুন 🔴 Instagram একাউন্ট খোলার তথ্য**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Username:** `{generated_user}`\n"
        f"🔑 **Password:** `{password}`\n"
        f"💎 **রেট:** *{selected_rate} টাকা*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**⚡ একাউন্ট তৈরি করে নিচে 2FA সেট বাটনে চাপ দিন:**"
    )
    kb = ReplyKeyboardMarkup([["⚜️ 2FA SET"], ["❌ বাতিল"]], resize_keyboard=True)
    info_msg = await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
    context.user_data["info_msg_id"] = info_msg.message_id
    return ENTERING_2FA

async def process_account_created(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⚜️ 2FA SET":
        prompt_msg = await update.message.reply_text(
            "**💠 2FA KEY দিন**",
            reply_markup=cancel_keyboard(), parse_mode="Markdown"
        )
        context.user_data.setdefault("bot_msg_ids", []).append(prompt_msg.message_id)
        context.user_data["bot_msg_ids"].append(update.message.message_id)
        return ENTERING_2FA
        
    user_key = text.strip().replace(" ", "")
    context.user_data.setdefault("bot_msg_ids", []).append(update.message.message_id)

    try:
        totp = pyotp.TOTP(user_key)
        live_code = totp.now()
    except Exception:
        err_msg = await update.message.reply_text("**❌ ভুল 2FA সিক্রেট কী! সঠিক কী দিন:**", parse_mode="Markdown")
        context.user_data["bot_msg_ids"].append(err_msg.message_id)
        return ENTERING_2FA

    context.user_data["task_2fa_key"] = user_key
    
    kb = ReplyKeyboardMarkup([["✅ অ্যাকাউন্ট খোলা শেষ"], ["❌ বাতিল"]], resize_keyboard=True)
    msg1 = await update.message.reply_text(
        "**একাউন্ট খোলা শেষ হলে নিচের বাটনকে চাপ দিন:**", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )
    
    msg2 = await update.message.reply_text(
        f"**নিচের বাটনে চাপ দিয়ে কোডটি কপি করুন ⤵️**\n`{live_code}`", 
        parse_mode="Markdown"
    )
    
    context.user_data.setdefault("bot_msg_ids", []).extend([msg1.message_id, msg2.message_id])
    return TASK_CONFIRM

async def copy_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

async def task_complete_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "✅ অ্যাকাউন্ট খোলা শেষ":
        user_id = update.effective_user.id
        current_date = get_custom_date()
        
        task_data = {
            "platform": "Instagram",
            "user_id": user_id,
            "name": update.effective_user.full_name,
            "insta_user": context.user_data.get("task_insta_user"),
            "insta_pass": context.user_data.get("task_pass"),
            "key_2fa": context.user_data.get("task_2fa_key"),
            "rate": context.user_data.get("task_rate"),
            "date": current_date,
            "status": "pending",
            "timestamp": datetime.datetime.now()
        }
        
        tasks_col.insert_one(task_data)
        users_col.update_one({"user_id": user_id}, {"$inc": {"review": 1}})
        
        info_id = context.user_data.get("info_msg_id")
        if info_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=info_id)
            except Exception:
                pass

        msg_ids = context.user_data.get("bot_msg_ids", [])
        for m_id in set(msg_ids):
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=m_id)
            except Exception:
                pass
        try:
            await update.message.delete()
        except Exception:
            pass

        context.user_data.clear()
        
        await update.message.reply_text(
            "**🎉 আপনার কাজটি সফলভাবে জমা দেওয়া হয়েছে। ১২-২৪ ঘন্টার মধ্যে ব্যালেন্স এ টাকা এড করে দেওয়া হবে।**", 
            reply_markup=main_keyboard(), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    return TASK_CONFIRM

async def fb_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "▶️ কাজের ভিডিও":
        conf = get_config()
        vid = conf.get("fb_video", "")
        if vid:
            try:
                await update.message.reply_video(video=vid, caption="**🎬 🔵 Facebook কাজের ভিডিও টিউটোরিয়াল**", parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("**⚠️ এখনো ভিডিও সেট করা হয়নি।**", parse_mode="Markdown")
        return FB_SELECT_TYPE

    if text == "📱 Number/Anymail":
        kb = ReplyKeyboardMarkup([["🍪 COOKIES SET"], ["❌ বাতিল"]], resize_keyboard=True)
        await update.message.reply_text("**🔷 অপশন সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
        return FB_SELECT_COOKIE_TYPE
    await update.message.reply_text("**❌ অকার্যকর অপশন!**", parse_mode="Markdown")
    return FB_SELECT_TYPE

async def fb_cookie_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🍪 COOKIES SET":
        conf = get_config()
        rate_buttons = [[f"💰 {r} টাকা"] for r in conf["fb_rates"]]
        rate_buttons.append(["❌ বাতিল"])
        kb = ReplyKeyboardMarkup(rate_buttons, resize_keyboard=True)
        await update.message.reply_text("**🔷 রেট সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
        return FB_SELECT_RATE
    await update.message.reply_text("**❌ অকার্যকর অপশন!**", parse_mode="Markdown")
    return FB_SELECT_COOKIE_TYPE

async def fb_rate_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        selected_rate = float(update.message.text.replace("💰", "").replace("টাকা", "").strip())
    except ValueError:
        await update.message.reply_text("**❌ সঠিক রেট সিলেক্ট করুন।**", parse_mode="Markdown")
        return FB_SELECT_RATE

    conf = get_config()
    fname, lname = generate_random_fb_name()
    password = conf["fb_pass"]

    context.user_data["task_platform"] = "Facebook"
    context.user_data["task_rate"] = selected_rate
    context.user_data["fb_fname"] = fname
    context.user_data["fb_lname"] = lname
    context.user_data["fb_pass"] = password

    msg = (
        "**✨ নতুন 🔵 Facebook একাউন্ট খোলার তথ্য**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **First Name:** `{fname}`\n"
        f"👤 **Last Name:** `{lname}`\n"
        f"🔑 **Password:** `{password}`\n"
        f"💎 **রেট:** *{selected_rate} টাকা*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "**⚙️ একাউন্ট তৈরি করে নিচে কুকিজ সেট বাটনে চাপ দিন:**"
    )
    kb = ReplyKeyboardMarkup([["🍪 COOKIES SET"], ["❌ বাতিল"]], resize_keyboard=True)
    info_msg = await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
    context.user_data["fb_info_msg_id"] = info_msg.message_id
    return FB_ENTER_UID

async def fb_process_account_created(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🍪 COOKIES SET":
        p_msg = await update.message.reply_text(
            "**💠 UID দিন**",
            reply_markup=cancel_keyboard(), parse_mode="Markdown"
        )
        context.user_data.setdefault("fb_msg_ids", []).append(p_msg.message_id)
        context.user_data["fb_msg_ids"].append(update.message.message_id)
        return FB_ENTER_COOKIES
    await update.message.reply_text("**❌ সঠিক বাটনে প্রেস করুন।**", parse_mode="Markdown")
    return FB_ENTER_UID

async def fb_get_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    context.user_data["fb_uid"] = uid
    context.user_data.setdefault("fb_msg_ids", []).append(update.message.message_id)
    p_msg2 = await update.message.reply_text("**💠 COOKIES দিন**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    context.user_data["fb_msg_ids"].append(p_msg2.message_id)
    return FB_TASK_CONFIRM

async def fb_get_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cookies = update.message.text.strip()
    context.user_data["fb_cookies"] = cookies
    context.user_data.setdefault("fb_msg_ids", []).append(update.message.message_id)
    
    kb = ReplyKeyboardMarkup([["✅ অ্যাকাউন্ট খোলা শেষ"], ["❌ বাতিল"]], resize_keyboard=True)
    msg_done = await update.message.reply_text("**✅ কুকিজ সফলভাবে গ্রহণ করা হয়েছে!**", parse_mode="Markdown", reply_markup=kb)
    context.user_data["fb_msg_ids"].append(msg_done.message_id)
    return FB_TASK_CONFIRM

async def fb_task_complete_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "✅ অ্যাকাউন্ট খোলা শেষ":
        user_id = update.effective_user.id
        current_date = get_custom_date()
        
        task_data = {
            "platform": "Facebook",
            "user_id": user_id,
            "name": update.effective_user.full_name,
            "fb_uid": context.user_data.get("fb_uid"),
            "fb_pass": context.user_data.get("fb_pass"),
            "fb_cookies": context.user_data.get("fb_cookies"),
            "rate": context.user_data.get("task_rate"),
            "date": current_date,
            "status": "pending",
            "timestamp": datetime.datetime.now()
        }
        
        tasks_col.insert_one(task_data)
        users_col.update_one({"user_id": user_id}, {"$inc": {"review": 1}})
        
        fb_info_id = context.user_data.get("fb_info_msg_id")
        if fb_info_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=fb_info_id)
            except Exception:
                pass

        fb_msg_ids = context.user_data.get("fb_msg_ids", [])
        for m_id in set(fb_msg_ids):
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=m_id)
            except Exception:
                pass
        try:
            await update.message.delete()
        except Exception:
            pass

        context.user_data.clear()
        
        await update.message.reply_text(
            "**🎉 আপনার কাজটি সফলভাবে জমা দেওয়া হয়েছে। ১২-২৪ ঘন্টার মধ্যে ব্যালেন্স এ টাকা এড করে দেওয়া হবে।**", 
            reply_markup=main_keyboard(), 
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    return await fb_get_cookies(update, context)

# ----------------- WITHDRAW SYSTEM (💸 টাকা উত্তোলন) -----------------
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_join_check(update, context): return ConversationHandler.END
    u = get_user(update.effective_user.id)
    if u["balance"] < (MIN_WITHDRAW + WITHDRAW_FEE):
        msg = f"**❌ পর্যাপ্ত ব্যালেন্স নেই! সর্বনিম্ন উত্তোলন: {MIN_WITHDRAW} টাকা**"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return ConversationHandler.END
    
    kb = ReplyKeyboardMarkup([
        ["BKASH", "NAGAD", "ROKET"],
        ["❌ বাতিল"]
    ], resize_keyboard=True)
    await update.message.reply_text("**🔷 পেমেন্ট মেথড সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
    return WITHDRAW_METHOD

async def withdraw_select_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conf = get_config()
    
    if text == "BKASH":
        vid = conf.get("bkash_video", "")
        if vid:
            try: await update.message.reply_video(video=vid, caption="**🎬 BKASH পেমেন্ট উত্তোলনের নিয়ম ও ভিডিও**", parse_mode="Markdown")
            except Exception: await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")
    elif text == "NAGAD":
        vid = conf.get("nagad_video", "")
        if vid:
            try: await update.message.reply_video(video=vid, caption="**🎬 NAGAD পেমেন্ট উত্তোলনের নিয়ম ও ভিডিও**", parse_mode="Markdown")
            except Exception: await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")
    elif text == "ROKET":
        vid = conf.get("roket_video", "")
        if vid:
            try: await update.message.reply_video(video=vid, caption="**🎬 ROKET পেমেন্ট উত্তোলনের নিয়ম ও ভিডিও**", parse_mode="Markdown")
            except Exception: await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")

    context.user_data["withdraw_method"] = text
    
    kb = ReplyKeyboardMarkup([
        ["▶️ উত্তোলনের ভিডিও"],
        ["❌ বাতিল"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        f"**📱 আপনার পার্সোনাল {text} অ্যাকাউন্ট নম্বরটি সেন্ড করুন:**", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )
    return WITHDRAW_NUMBER

async def withdraw_get_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conf = get_config()
    method = context.user_data.get("withdraw_method", "BKASH")
    
    if text == "▶️ উত্তোলনের ভিডিও":
        vid = ""
        if method == "BKASH": vid = conf.get("bkash_video", "")
        elif method == "NAGAD": vid = conf.get("nagad_video", "")
        elif method == "ROKET": vid = conf.get("roket_video", "")
        
        if vid:
            try: await update.message.reply_video(video=vid, caption=f"**🎬 {method} পেমেন্ট উত্তোলনের ভিডিও টিউটোরিয়াল**", parse_mode="Markdown")
            except Exception: await update.message.reply_text(f"**🎬 ভিডিও লিংক:** `{vid}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("**⚠️ এই মেথডের জন্য কোনো ভিডিও নেই।**", parse_mode="Markdown")
        return WITHDRAW_NUMBER

    context.user_data["withdraw_number"] = text
    await update.message.reply_text("**💵 কত টাকা উত্তোলন করতে চান লিখুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return WITHDRAW_AMOUNT

async def withdraw_process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("**❌ সঠিক টাকার পরিমাণ লিখুন:**", parse_mode="Markdown")
        return WITHDRAW_AMOUNT

    user_id = update.effective_user.id
    u = get_user(user_id)
    if u["balance"] < (amount + WITHDRAW_FEE):
        await update.message.reply_text("**❌ পর্যাপ্ত ব্যালেন্স নেই!**", parse_mode="Markdown")
        return WITHDRAW_AMOUNT

    withdraw_id = withdraws_col.count_documents({}) + 1
    req = {
        "id": withdraw_id,
        "user_id": user_id,
        "name": update.effective_user.full_name,
        "method": context.user_data["withdraw_method"],
        "number": context.user_data["withdraw_number"],
        "amount": amount,
        "fee": WITHDRAW_FEE,
        "status": "pending"
    }
    withdraws_col.insert_one(req)
    users_col.update_one({"user_id": user_id}, {"$inc": {"balance": -(amount+WITHDRAW_FEE), "pending_withdraw": amount}})
    
    await update.message.reply_text("**🎉 উত্তোলন রিকোয়েস্ট সফলভাবে জমা হয়েছে!**", reply_markup=main_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

# ----------------- ADMIN PANEL & ACTIONS -----------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("**🛡️ এডমিন কন্ট্রোল প্যানেল:**", reply_markup=admin_keyboard(), parse_mode="Markdown")

async def admin_withdraw_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    pendings = list(withdraws_col.find({"status": "pending"}))
    if not pendings:
        await update.message.reply_text("**✨ বর্তমানে কোনো পেন্ডিং উইথড্র নেই।**", parse_mode="Markdown")
        return
    for w in pendings:
        msg = (
            f"🆔 আইডি: `#{w['id']}`\n"
            f"👤 ইউজার: {w['name']} (`{w['user_id']}`)\n"
            f"💰 পরিমাণ: *{w['amount']} টাকা*\n"
            f"📞 মেথড: {w['method']} - `{w['number']}`\n\n"
            f"👇 `/approve_{w['id']}` | `/reject_{w['id']}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_handle_withdraw_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = update.message.text
    if text.startswith("/approve_"):
        wid = int(text.split("_")[1])
        w = withdraws_col.find_one({"id": wid, "status": "pending"})
        if w:
            withdraws_col.update_one({"id": wid}, {"$set": {"status": "approved"}})
            users_col.update_one({"user_id": w["user_id"]}, {"$inc": {"pending_withdraw": -w["amount"]}})
            await update.message.reply_text(f"**✅ উইথড্র `#{wid}` অ্যাপ্রুভড!**", parse_mode="Markdown")
            try:
                await context.bot.send_message(w["user_id"], f"**🎉 আপনার {w['amount']} টাকার পেমেন্ট সফল হয়েছে!**", parse_mode="Markdown")
            except Exception: pass
    elif text.startswith("/reject_"):
        wid = int(text.split("_")[1])
        w = withdraws_col.find_one({"id": wid, "status": "pending"})
        if w:
            withdraws_col.update_one({"id": wid}, {"$set": {"status": "rejected"}})
            refund_amount = w["amount"] + w["fee"]
            users_col.update_one({"user_id": w["user_id"]}, {"$inc": {"balance": refund_amount, "pending_withdraw": -w["amount"]}})
            await update.message.reply_text(f"**❌ উইথড্র `#{wid}` বাতিল!**", parse_mode="Markdown")
            try:
                await context.bot.send_message(w["user_id"], "**❌ আপনার পেমেন্ট রিকোয়েস্ট বাতিল করা হয়েছে।**", parse_mode="Markdown")
            except Exception: pass

async def admin_task_on_off_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    conf = get_config()
    insta_status = "🟢 ON" if conf.get("insta_task_active", True) else "🔴 OFF"
    fb_status = "🟢 ON" if conf.get("fb_task_active", True) else "🔴 OFF"

    kb = ReplyKeyboardMarkup([
        [f"🔴 Instagram: {insta_status}", f"🔵 Facebook: {fb_status}"],
        ["🔙 কাস্টমাইজ মেনু"]
    ], resize_keyboard=True)
    await update.message.reply_text("**🔌 কাজ অন/অফ প্যানেল:**", reply_markup=kb, parse_mode="Markdown")
    return ADMIN_TASK_ON_OFF_MENU

async def admin_toggle_task_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    text = update.message.text
    conf = get_config()

    if "Instagram" in text:
        current = conf.get("insta_task_active", True)
        new_val = not current
        config_col.update_one({"id": "settings"}, {"$set": {"insta_task_active": new_val}})
        await update.message.reply_text("**✅ 🔴 Instagram কাজ পরিবর্তন করা হয়েছে!**", parse_mode="Markdown")
    elif "Facebook" in text:
        current = conf.get("fb_task_active", True)
        new_val = not current
        config_col.update_one({"id": "settings"}, {"$set": {"fb_task_active": new_val}})
        await update.message.reply_text("**✅ 🔵 Facebook কাজ পরিবর্তন করা হয়েছে!**", parse_mode="Markdown")
    elif text == "🔙 কাস্টমাইজ মেনু":
        await update.message.reply_text("**⚙️ কাস্টমাইজ প্যানেল:**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END

    conf = get_config()
    insta_status = "🟢 ON" if conf.get("insta_task_active", True) else "🔴 OFF"
    fb_status = "🟢 ON" if conf.get("fb_task_active", True) else "🔴 OFF"
    kb = ReplyKeyboardMarkup([
        [f"🔴 Instagram: {insta_status}", f"🔵 Facebook: {fb_status}"],
        ["🔙 কাস্টমাইজ মেনু"]
    ], resize_keyboard=True)
    await update.message.reply_text("**🔌 আপডেট সম্পন্ন।**", reply_markup=kb)
    return ADMIN_TASK_ON_OFF_MENU

# --- ADMIN METHOD MANAGEMENT ---
async def admin_method_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        ["➕ মেথড যোগ", "🗑️ মেথড ডিলিট"],
        ["🔙 কাস্টমাইজ মেনু"]
    ], resize_keyboard=True)
    await update.message.reply_text("**📁 মেথড ম্যানেজমেন্ট:**", reply_markup=kb, parse_mode="Markdown")
    return ADMIN_METHOD_MENU

async def admin_method_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    text = update.message.text
    if text == "➕ মেথড যোগ":
        await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
        return ADMIN_ADD_METHOD_PLATFORM
    elif text == "🗑️ মেথড ডিলিট":
        await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
        return ADMIN_DEL_METHOD_PLATFORM
    elif text == "🔙 কাস্টমাইজ মেনু":
        await update.message.reply_text("**⚙️ কাস্টমাইজ প্যানেল:**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    return ADMIN_METHOD_MENU

async def admin_add_method_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Instagram" in text or "Facebook" in text:
        context.user_data["new_method_platform"] = "Instagram" if "Instagram" in text else "Facebook"
        await update.message.reply_text("**✍️ মেথডের নাম দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
        return ADMIN_ADD_METHOD_NAME
    await update.message.reply_text("**❌ সঠিক প্ল্যাটফর্ম সিলেক্ট করুন।**", parse_mode="Markdown")
    return ADMIN_ADD_METHOD_PLATFORM

async def admin_add_method_name_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_method_name"] = update.message.text.strip()
    await update.message.reply_text("**📤 এখন ভিডিও ফাইল বা লিংক সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_ADD_METHOD_FILE

async def admin_save_new_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file_id = update.message.video.file_id
    elif update.message.document and update.message.document.mime_type.startswith('video/'):
        file_id = update.message.document.file_id
    elif update.message.text:
        file_id = update.message.text.strip()
    else:
        await update.message.reply_text("**❌ সঠিক ভিডিও দিন।**", parse_mode="Markdown")
        return ADMIN_ADD_METHOD_FILE

    platform = context.user_data.get("new_method_platform", "Instagram")
    name = context.user_data.get("new_method_name", "Method")

    methods_col.insert_one({
        "platform": platform,
        "name": name,
        "file_id": file_id
    })

    await update.message.reply_text("**✅ সফলভাবে সেভ হয়েছে!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_del_method_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Instagram" in text or "Facebook" in text:
        platform = "Instagram" if "Instagram" in text else "Facebook"
        context.user_data["del_method_platform"] = platform
        
        methods = list(methods_col.find({"platform": platform}))
        if not methods:
            await update.message.reply_text("**⚠️ কোনো মেথড নেই।**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
            return ConversationHandler.END
        
        keyboard_rows = [[m['name']] for m in methods]
        keyboard_rows.append(["❌ বাতিল"])
        kb = ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True)
        
        await update.message.reply_text("**🗑️ ডিলিট করার জন্য মেথডে চাপ দিন:**", reply_markup=kb, parse_mode="Markdown")
        return ADMIN_DEL_METHOD_SELECT
    
    await update.message.reply_text("**❌ সঠিক প্ল্যাটফর্ম সিলেক্ট করুন।**", parse_mode="Markdown")
    return ADMIN_DEL_METHOD_PLATFORM

async def admin_delete_method_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name_to_del = update.message.text.strip()
    platform = context.user_data.get("del_method_platform", "Instagram")
    
    res = methods_col.delete_one({"platform": platform, "name": name_to_del})
    if res.deleted_count > 0:
        await update.message.reply_text("**✅ সফলভাবে ডিলিট করা হয়েছে!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text("**❌ মেথড পাওয়া যায়নি!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END

# ----------------- ADMIN SETTINGS & VIDEOS -----------------
async def admin_video_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 ভিডিও সেট ম্যানেজমেন্ট প্যানেল:**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_prompt_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**📢 নতুন অফিশিয়াল চ্যানেল ইউজারনেম দিন (যেমন: `@mychannel`):**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_CHANNEL

async def save_admin_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_col.update_one({"id": "settings"}, {"$set": {"required_channel": update.message.text.strip()}})
    await update.message.reply_text("**✅ চ্যানেল ইউজারনেম সফলভাবে আপডেট করা হয়েছে!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def admin_prompt_insta_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 🔴 Instagram কাজের ভিডিও ফাইল বা লিংক সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_INSTA_VID

async def save_admin_insta_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.text.strip())
    config_col.update_one({"id": "settings"}, {"$set": {"insta_video": vid}})
    await update.message.reply_text("**✅ Instagram ভিডিও সফলভাবে সেট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_prompt_fb_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 🔵 Facebook কাজের ভিডিও ফাইল বা লিংক সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_FB_VID

async def save_admin_fb_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.text.strip())
    config_col.update_one({"id": "settings"}, {"$set": {"fb_video": vid}})
    await update.message.reply_text("**✅ Facebook ভিডিও সফলভাবে সেট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_prompt_bkash_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 BKASH পেমেন্ট উত্তোলনের ভিডিও সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_BKASH_VID

async def save_admin_bkash_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.text.strip())
    config_col.update_one({"id": "settings"}, {"$set": {"bkash_video": vid}})
    await update.message.reply_text("**✅ BKASH ভিডিও সফলভাবে সেট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_prompt_nagad_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 NAGAD পেমেন্ট উত্তোলনের ভিডিও সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_NAGAD_VID

async def save_admin_nagad_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.text.strip())
    config_col.update_one({"id": "settings"}, {"$set": {"nagad_video": vid}})
    await update.message.reply_text("**✅ NAGAD ভিডিও সফলভাবে সেট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_prompt_roket_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎬 ROKET পেমেন্ট উত্তোলনের ভিডিও সেন্ড করুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_ROKET_VID

async def save_admin_roket_vid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid = update.message.video.file_id if update.message.video else (update.message.document.file_id if update.message.document else update.message.text.strip())
    config_col.update_one({"id": "settings"}, {"$set": {"roket_video": vid}})
    await update.message.reply_text("**✅ ROKET ভিডিও সফলভাবে সেট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_delete_video_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    kb = ReplyKeyboardMarkup([
        ["🗑️ Insta Video Delete", "🗑️ FB Video Delete"],
        ["🗑️ BKASH Video Delete", "🗑️ NAGAD Video Delete", "🗑️ ROKET Video Delete"],
        ["🔙 ভিডিও মেনু"]
    ], resize_keyboard=True)
    await update.message.reply_text("**🗑️ কোন ভিডিওটি ডিলিট করতে চান সিলেক্ট করুন:**", reply_markup=kb, parse_mode="Markdown")
    return ADMIN_VIDEO_MENU

async def admin_delete_video_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    field_map = {
        "🗑️ Insta Video Delete": "insta_video",
        "🗑️ FB Video Delete": "fb_video",
        "🗑️ BKASH Video Delete": "bkash_video",
        "🗑️ NAGAD Video Delete": "nagad_video",
        "🗑️ ROKET Video Delete": "roket_video"
    }
    if text in field_map:
        config_col.update_one({"id": "settings"}, {"$set": {field_map[text]: ""}})
        await update.message.reply_text("**✅ সফলভাবে ভিডিও ডিলিট করা হয়েছে!**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
        return ADMIN_VIDEO_MENU
    elif text == "🔙 ভিডিও মেনু":
        await update.message.reply_text("**🎬 ভিডিও সেট ম্যানেজমেন্ট প্যানেল:**", reply_markup=admin_video_menu_keyboard(), parse_mode="Markdown")
        return ADMIN_VIDEO_MENU
    return ADMIN_VIDEO_MENU

# ----------------- ADMIN USERS & MANAGEMENT -----------------
def sync_generate_users_file():
    users = list(users_col.find({}))
    if not users: return None
    excel_data = []
    for u in users:
        excel_data.append({
            "USER ID": u.get("user_id"),
            "TG AC NAME": u.get("name", "Unknown"),
            "AC BLANCE": u.get("balance", 0.0),
            "PENDING KAJ": u.get("review", 0),
            "MOT AY": u.get("total_earned", 0.0),
            "REVIEW KAJ": u.get("completed", 0),
            "BLANCE": u.get("balance", 0.0)
        })
    df = pd.DataFrame(excel_data)
    filename = f"Total_Users_{datetime.datetime.now().strftime('%d-%m-%Y')}.xlsx"
    df.to_excel(filename, index=False)
    return filename

async def admin_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    status_msg = await update.message.reply_text("**⏳ ইউজার ফাইল তৈরি হচ্ছে...**", parse_mode="Markdown")
    filename = await asyncio.to_thread(sync_generate_users_file)
    total_users = users_col.count_documents({})
    if not filename:
        await status_msg.edit_text("**⚠️ ইউজার পাওয়া যায়নি।**", parse_mode="Markdown")
        return
    await status_msg.delete()
    await update.message.reply_document(document=open(filename, "rb"), caption=f"**👥 মোট ইউজার:** `{total_users}`", parse_mode="Markdown")
    if os.path.exists(filename): os.remove(filename)

async def admin_prompt_user_mgmt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**👥 ম্যানেজ করার জন্য ইউজারের Telegram ID পাঠান:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_USER_MGMT_INPUT

async def admin_get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("**❌ সঠিক ইউজার আইডি দিন:**", parse_mode="Markdown")
        return ADMIN_USER_MGMT_INPUT
    target_id = int(text)
    user = users_col.find_one({"user_id": target_id})
    if not user:
        await update.message.reply_text("**⚠️ ইউজার পাওয়া যায়নি!**", parse_mode="Markdown")
        return ADMIN_USER_MGMT_INPUT
    context.user_data["mgmt_user_id"] = target_id
    msg = (
        f"👤 **User ID:** `{target_id}`\n"
        f"💵 **Balance:** `{user.get('balance', 0.0)}` টাকা\n"
        f"✅ **Completed Tasks:** `{user.get('completed', 0)}`\n"
        f"🔍 **Pending/Review Tasks:** `{user.get('review', 0)}`\n"
        f"🏆 **Total Earned:** `{user.get('total_earned', 0.0)}` টাকা"
    )
    kb = ReplyKeyboardMarkup([
        ["💵 ব্যালেন্স পরিবর্তন", "✅ সফল কাজ পরিবর্তন"],
        ["⏳ পেন্ডিং কাজ পরিবর্তন", "🏆 মোট আয় পরিবর্তন"],
        ["🔙 এডমিন মেনু"]
    ], resize_keyboard=True)
    await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    return ADMIN_USER_EDIT_CHOICE

async def admin_user_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    mapping = {
        "💵 ব্যালেন্স পরিবর্তন": "balance", 
        "✅ সফল কাজ পরিবর্তন": "completed",
        "⏳ পেন্ডিং কাজ পরিবর্তন": "review",
        "🏆 মোট আয় পরিবর্তন": "total_earned"
    }
    if choice not in mapping:
        await update.message.reply_text("**❌ সঠিক অপশন সিলেক্ট করুন।**", parse_mode="Markdown")
        return ADMIN_USER_EDIT_CHOICE
    context.user_data["mgmt_field"] = mapping[choice]
    await update.message.reply_text("**✍️ নতুন মান (Value) লিখুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_USER_EDIT_VALUE

async def admin_user_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("**❌ সঠিক সংখ্যা লিখুন:**", parse_mode="Markdown")
        return ADMIN_USER_EDIT_VALUE
    users_col.update_one({"user_id": context.user_data.get("mgmt_user_id")}, {"$set": {context.user_data.get("mgmt_field"): val}})
    await update.message.reply_text("**✅ সফলভাবে আপডেট হয়েছে!**", reply_markup=admin_keyboard(), parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def admin_database_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    total_users = users_col.count_documents({})
    total_tasks = tasks_col.count_documents({})
    total_withdraws = withdraws_col.count_documents({})
    
    # তারিখ এবং প্ল্যাটফর্ম অনুযায়ী আইডি জমার হিস্ট্রি বের করা
    pipeline = [
        {"$group": {"_id": {"date": "$date", "platform": "$platform"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": -1}}
    ]
    date_stats = list(tasks_col.aggregate(pipeline))
    
    msg = (
        "**🗄️ Database & Task Summary Dashboard**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 **Total Users:** `{total_users}` জন\n"
        f"📋 **Total Tasks:** `{total_tasks}` টি\n"
        f"💸 **Total Withdraws:** `{total_withdraws}` টি\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📅 **তারিখ ও প্ল্যাটফর্ম অনুযায়ী জমাকৃত আইডি:**\n"
    )
    
    if not date_stats:
        msg += "_কোনো টাস্ক ডাটা পাওয়া যায়নি।_"
    else:
        for stat in date_stats:
            d = stat["_id"].get("date", "Unknown")
            p = stat["_id"].get("platform", "Unknown")
            cnt = stat["count"]
            p_icon = "🔴" if p == "Instagram" else "🔵"
            msg += f"• Date: `{d}` | {p_icon} {p}: `{cnt}` টি\n"
            
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=admin_keyboard())

async def admin_prompt_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**📢 ব্রডকাস্ট মেসেজ লিখুন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_BROADCAST_MSG

async def admin_send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    all_users = list(users_col.find({}, {"user_id": 1}))
    success = 0
    for u in all_users:
        try:
            await context.bot.send_message(chat_id=u["user_id"], text=f"**📢 নোটিশ:**\n\n{msg_text}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.03)
        except Exception: pass
    await update.message.reply_text(f"**📢 সফলভাবে পাঠানো হয়েছে:** {success} জন", reply_markup=admin_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def admin_prompt_insta_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🔑 নতুন 🔴 Instagram পাসওয়ার্ড দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_INSTA_PASS

async def admin_prompt_fb_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🔑 নতুন 🔵 Facebook পাসওয়ার্ড দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_FB_PASS

async def admin_prompt_insta_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**💵 🔴 Instagram রেট দিন (যেমন: 5, 6, 7):**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_INSTA_RATE

async def admin_prompt_fb_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**💵 🔵 Facebook রেট দিন (যেমন: 5, 6, 7, 8):**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_FB_RATE

async def admin_prompt_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🎧 নতুন সাপোর্ট লিংক দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_SET_SUPPORT

async def save_admin_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_col.update_one({"id": "settings"}, {"$set": {"support_link": update.message.text.strip()}})
    await update.message.reply_text("**✅ আপডেট সম্পন্ন!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def save_admin_insta_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_col.update_one({"id": "settings"}, {"$set": {"insta_pass": update.message.text.strip()}})
    await update.message.reply_text("**✅ আপডেট সম্পন্ন!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def save_admin_fb_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_col.update_one({"id": "settings"}, {"$set": {"fb_pass": update.message.text.strip()}})
    await update.message.reply_text("**✅ আপডেট সম্পন্ন!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def save_admin_insta_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rates = [float(r.strip()) for r in update.message.text.split(",")]
        config_col.update_one({"id": "settings"}, {"$set": {"insta_rates": rates}})
        await update.message.reply_text("**✅ সেভ হয়েছে!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    except ValueError:
        return ADMIN_SET_INSTA_RATE
    return ConversationHandler.END

async def save_admin_fb_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rates = [float(r.strip()) for r in update.message.text.split(",")]
        config_col.update_one({"id": "settings"}, {"$set": {"fb_rates": rates}})
        await update.message.reply_text("**✅ সেভ হয়েছে!**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")
    except ValueError:
        return ADMIN_SET_FB_RATE
    return ConversationHandler.END

# Excel File and Report handlers
async def admin_prompt_file_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
    return ADMIN_SELECT_FILE_PLATFORM

async def admin_select_file_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["download_platform"] = "Instagram" if "Instagram" in text else "Facebook"
    await update.message.reply_text("**📅 ফাইলের তারিখ দিন (যেমন: DD-MM-YYYY):**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_GET_DATE_FILE

def sync_generate_file(date_str, target_platform):
    tasks = list(tasks_col.find({"date": date_str, "platform": target_platform}))
    if not tasks: return None
    excel_data = []
    for t in tasks:
        user_doc = users_col.find_one({"user_id": t.get("user_id")})
        tg_name = user_doc.get("name", "Unknown") if user_doc else "Unknown"
        
        if target_platform == "Facebook":
            excel_data.append({
                "USER ID": t.get("user_id"),
                "TG AC NAME": tg_name,
                "PLATFROM": "Facebook",
                "FB AC UID": t.get("fb_uid"),
                "PASSWORD": t.get("fb_pass"),
                "COOKIES": t.get("fb_cookies"),
                "RET": t.get("rate")
            })
        else:
            excel_data.append({
                "USER ID": t.get("user_id"),
                "TG AC NAME": tg_name,
                "PLATFROM": "Instagram",
                "USERNAME": t.get("insta_user"),
                "PASSWORD": t.get("insta_pass"),
                "2FA KEY": t.get("key_2fa"),
                "RET": t.get("rate")
            })
            
    df = pd.DataFrame(excel_data)
    filename = f"{target_platform}_Tasks_{date_str}.xlsx"
    df.to_excel(filename, index=False)
    return filename

async def admin_generate_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    target_platform = context.user_data.get("download_platform", "Instagram")
    p_label = "🔴 Instagram" if target_platform == "Instagram" else "🔵 Facebook"
    filename = await asyncio.to_thread(sync_generate_file, date_str, target_platform)
    if not filename:
        await update.message.reply_text("**❌ কোনো টাস্ক নেই।**", reply_markup=admin_all_tasks_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_document(document=open(filename, "rb"), caption=f"**📁 {p_label} File**", parse_mode="Markdown")
    if os.path.exists(filename): os.remove(filename)
    await update.message.reply_text("**⚙️ টাস্ক সেন্টার:**", reply_markup=admin_all_tasks_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def admin_prompt_report_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    await update.message.reply_text("**🔷 প্ল্যাটফর্ম সিলেক্ট করুন:**", reply_markup=platform_choice_keyboard(), parse_mode="Markdown")
    return ADMIN_SELECT_REPORT_PLATFORM

async def admin_select_report_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["report_platform"] = "Instagram" if "Instagram" in text else "Facebook"
    await update.message.reply_text("**📅 রিপোর্টের তারিখ দিন:**", reply_markup=cancel_keyboard(), parse_mode="Markdown")
    return ADMIN_GET_DATE_REPORT

async def admin_receive_report_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["report_date"] = update.message.text.strip()
    await update.message.reply_text("**📤 কালার করা এক্সেল ফাইল পাঠান:**", parse_mode="Markdown")
    return ADMIN_UPLOAD_REPORT

def sync_process_excel_report(file_path, report_date, target_platform):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    approved, rejected = [], []
    for row in range(1, sheet.max_row + 1):
        cell = sheet.cell(row=row, column=1)
        target_id = str(cell.value).strip() if cell.value else None
        if not target_id: continue
        query = {"date": report_date, "status": "pending", "platform": target_platform}
        if target_platform == "Facebook": query["fb_uid"] = target_id
        else: query["insta_user"] = target_id
        task = tasks_col.find_one(query)
        if not task: continue
        is_green = False
        if cell.font and cell.font.color and cell.font.color.rgb:
            font_rgb = str(cell.font.color.rgb).upper()
            if font_rgb in ["FF00B050", "00B050", "FF008000", "008000", "92D050", "FF92D050", "00FF00", "FF00FF00"]:
                is_green = True
        if not is_green and cell.fill and cell.fill.start_color and cell.fill.start_color.rgb:
            fill_rgb = str(cell.fill.start_color.rgb).upper()
            if fill_rgb in ["FF00FF00", "00FF00", "FF008000", "92D050", "00B050", "FF00B050"]:
                is_green = True
        user_id, rate = task["user_id"], task["rate"]
        if is_green:
            tasks_col.update_one({"_id": task["_id"]}, {"$set": {"status": "approved"}})
            users_col.update_one({"user_id": user_id}, {"$inc": {"balance": rate, "total_earned": rate, "completed": 1, "review": -1}})
            approved.append((user_id, rate))
        else:
            tasks_col.update_one({"_id": task["_id"]}, {"$set": {"status": "rejected"}})
            users_col.update_one({"user_id": user_id}, {"$inc": {"review": -1}})
            rejected.append(user_id)
    return approved, rejected

async def admin_process_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(('.xlsx', '.xls')):
        await update.message.reply_text("**❌ এক্সেল ফাইল পাঠান!**", parse_mode="Markdown")
        return ADMIN_UPLOAD_REPORT
    file = await doc.get_file()
    file_path = "temp_report.xlsx"
    await file.download_to_drive(file_path)
    p_platform = context.user_data.get("report_platform")
    approved, rejected = await asyncio.to_thread(sync_process_excel_report, file_path, context.user_data.get("report_date"), p_platform)
    if os.path.exists(file_path): os.remove(file_path)
    p_label = "🔴 Instagram" if p_platform == "Instagram" else "🔵 Facebook"
    await update.message.reply_text(f"**📊 {p_label} রিপোর্ট আপডেট সম্পন্ন!**\n✅ অনুমোদিত: {len(approved)} | ❌ বাতিল: {len(rejected)}", reply_markup=admin_all_tasks_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

# ----------------- FLASK DUMMY SERVER -----------------
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot is running!"
def run_web(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
def keep_alive(): Thread(target=run_web).start()

# ----------------- MAIN RUNNER -----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    global_cancel_filter = filters.Regex(r"^❌ বাতিল$")
    global_back_filter = filters.Regex(r"^(🔙 পেছনে যান|🔙 মূল মেনু|🔙 এডমিন মেনু|🔙 কাস্টমাইজ মেনু|🔙 ভিডিও মেনু)$")
    main_menu_filter = filters.Regex(r"^(💰 ব্যালেন্স|🎁 রেফারেল|🎧 সাপোর্ট)$")

    conv_method = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📚 মেথড$"), method_start)],
        states={
            METHOD_SELECT_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), method_platform_selected)],
            METHOD_AVAILABLE_MENU: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), method_show_titles)],
            METHOD_SEND_VIDEO: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), method_send_video)]
        },
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler), MessageHandler(main_menu_filter, cancel_handler)]
    )

    conv_work = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🎯 কাজ শুরু$"), work_start)],
        states={
            WORK_SELECT_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), work_platform_selected)],
            WORK_SELECT_TYPE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), work_type_selected)],
            WORK_SELECT_RATE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), work_rate_selected)],
            ENTERING_2FA: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), process_account_created)],
            TASK_CONFIRM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), task_complete_done)],
            FB_SELECT_TYPE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_type_selected)],
            FB_SELECT_COOKIE_TYPE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_cookie_type_selected)],
            FB_SELECT_RATE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_rate_selected)],
            FB_ENTER_UID: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_process_account_created)],
            FB_ENTER_COOKIES: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_get_uid)],
            FB_TASK_CONFIRM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), fb_task_complete_done)],
        },
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler), MessageHandler(main_menu_filter, cancel_handler)]
    )

    conv_withdraw = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^💸 টাকা উত্তোলন$"), withdraw_start)],
        states={
            WITHDRAW_METHOD: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), withdraw_select_method)],
            WITHDRAW_NUMBER: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), withdraw_get_number)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), withdraw_process_amount)],
        },
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler), MessageHandler(main_menu_filter, cancel_handler)]
    )

    conv_admin_broadcast = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📢 ব্রডকাস্ট$"), admin_prompt_broadcast)],
        states={ADMIN_BROADCAST_MSG: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_send_broadcast)]},
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler)]
    )

    conv_admin_user_mgmt = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^👥 ইউজার কন্ট্রোল$"), admin_prompt_user_mgmt)],
        states={
            ADMIN_USER_MGMT_INPUT: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_get_user_info)],
            ADMIN_USER_EDIT_CHOICE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_user_edit_choice)],
            ADMIN_USER_EDIT_VALUE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_user_edit_save)]
        },
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler)]
    )

    conv_admin_settings = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🔌 কাজ অন/অফ$"), admin_task_on_off_menu),
            MessageHandler(filters.Regex(r"^📢 চ্যানেল সেট$"), admin_prompt_channel),
            MessageHandler(filters.Regex(r"^🎬 ভিডিও ম্যানেজমেন্ট$"), admin_video_menu_start),
            MessageHandler(filters.Regex(r"^🔑 🔴 Instagram পাসওয়ার্ড$"), admin_prompt_insta_pass),
            MessageHandler(filters.Regex(r"^🔑 🔵 Facebook পাসওয়ার্ড$"), admin_prompt_fb_pass),
            MessageHandler(filters.Regex(r"^💵 🔴 Instagram রেট$"), admin_prompt_insta_rates),
            MessageHandler(filters.Regex(r"^💵 🔵 Facebook রেট$"), admin_prompt_fb_rates),
            MessageHandler(filters.Regex(r"^🎧 সাপোর্ট লিংক$"), admin_prompt_support),
            MessageHandler(filters.Regex(r"^📁 মেথড কন্ট্রোল$"), admin_method_menu),
            MessageHandler(filters.Regex(r"^📥 ফাইল ডাউনলোড$"), admin_prompt_file_platform),
            MessageHandler(filters.Regex(r"^📤 রিপোর্ট জমা$"), admin_prompt_report_platform)
        ],
        states={
            ADMIN_TASK_ON_OFF_MENU: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_toggle_task_status)],
            ADMIN_SET_CHANNEL: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_channel)],
            ADMIN_VIDEO_MENU: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), lambda u, c: (
                admin_delete_video_prompt(u, c) if "🗑️ ভিডিও ডিলিট" in u.message.text else
                admin_delete_video_exec(u, c) if "Delete" in u.message.text else
                admin_prompt_insta_vid(u, c) if "Instagram" in u.message.text else
                admin_prompt_fb_vid(u, c) if "Facebook" in u.message.text else
                admin_prompt_bkash_vid(u, c) if "BKASH" in u.message.text else
                admin_prompt_nagad_vid(u, c) if "NAGAD" in u.message.text else
                admin_prompt_roket_vid(u, c) if "ROKET" in u.message.text else
                smart_back_handler(u, c)
            ))],
            ADMIN_SET_INSTA_VID: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), save_admin_insta_vid)],
            ADMIN_SET_FB_VID: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), save_admin_fb_vid)],
            ADMIN_SET_BKASH_VID: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), save_admin_bkash_vid)],
            ADMIN_SET_NAGAD_VID: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), save_admin_nagad_vid)],
            ADMIN_SET_ROKET_VID: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), save_admin_roket_vid)],
            ADMIN_SET_INSTA_PASS: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_insta_pass)],
            ADMIN_SET_FB_PASS: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_fb_pass)],
            ADMIN_SET_INSTA_RATE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_insta_rates)],
            ADMIN_SET_FB_RATE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_fb_rates)],
            ADMIN_SET_SUPPORT: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), save_admin_support)],
            ADMIN_METHOD_MENU: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_method_actions)],
            ADMIN_ADD_METHOD_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_add_method_platform)],
            ADMIN_ADD_METHOD_NAME: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_add_method_name_get)],
            ADMIN_ADD_METHOD_FILE: [MessageHandler((filters.VIDEO | filters.Document.VIDEO | filters.TEXT) & (~global_cancel_filter) & (~global_back_filter), admin_save_new_method)],
            ADMIN_DEL_METHOD_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_del_method_platform)],
            ADMIN_DEL_METHOD_SELECT: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_delete_method_exec)],
            ADMIN_SELECT_FILE_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_select_file_platform)],
            ADMIN_GET_DATE_FILE: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_generate_file)],
            ADMIN_SELECT_REPORT_PLATFORM: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_select_report_platform)],
            ADMIN_GET_DATE_REPORT: [MessageHandler(filters.TEXT & (~global_cancel_filter) & (~global_back_filter), admin_receive_report_date)],
            ADMIN_UPLOAD_REPORT: [MessageHandler(filters.Document.ALL & (~global_cancel_filter) & (~global_back_filter), admin_process_report)]
        },
        fallbacks=[MessageHandler(global_cancel_filter, cancel_handler), MessageHandler(global_back_filter, smart_back_handler)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(CallbackQueryHandler(inline_join_check_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(copy_callback_handler, pattern="^copy_code_"))
    
    app.add_handler(MessageHandler(filters.Regex(r"^💰 ব্যালেন্স$"), balance))
    app.add_handler(MessageHandler(filters.Regex(r"^🎁 রেফারেল$"), refer_info))
    app.add_handler(MessageHandler(filters.Regex(r"^🎧 সাপোর্ট$"), support_info))
    app.add_handler(MessageHandler(filters.Regex(r"^🗄️ ডাটাবেজ$"), admin_database_management))
    app.add_handler(MessageHandler(filters.Regex(r"^👥 মোট ইউজার$"), admin_total_users))
    
    app.add_handler(conv_method)
    app.add_handler(conv_work)
    app.add_handler(conv_withdraw)
    app.add_handler(conv_admin_broadcast)
    app.add_handler(conv_admin_user_mgmt)
    app.add_handler(conv_admin_settings)

    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ কাস্টমাইজ$"), lambda u,c: u.message.reply_text("**⚙️ কাস্টমাইজ প্যানেল:**", reply_markup=admin_custom_keyboard(), parse_mode="Markdown")))
    app.add_handler(MessageHandler(filters.Regex(r"^💸 উইথড্র কন্ট্রোল$"), admin_withdraw_custom))
    app.add_handler(MessageHandler(filters.Regex(r"^📁 টাস্ক সেন্টার$"), lambda u,c: u.message.reply_text("**📁 টাস্ক সেন্টার:**", reply_markup=admin_all_tasks_keyboard(), parse_mode="Markdown")))

    app.add_handler(MessageHandler(filters.Regex(r"^/(approve|reject)_\d+$"), admin_handle_withdraw_actions))
    app.add_handler(MessageHandler(global_cancel_filter, cancel_handler))
    app.add_handler(MessageHandler(global_back_filter, smart_back_handler))

    keep_alive()
    print("🚀 বট সফলভাবে রান হচ্ছে!")
    app.run_polling()

if __name__ == "__main__":
    main()
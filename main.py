import os
import telebot
import random
import sqlite3
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("8850736456:AAFavFv_tXs5d5tEMErpwkLI11tMuBATtNk")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    join_date TEXT,
    expiry_date TEXT,
    plan TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT
)
""")

conn.commit()

# =========================
# HELPERS
# =========================

def user_exists(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def add_user(user_id):
    join_date = datetime.now()
    expiry_date = join_date + timedelta(days=7)

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?)",
        (
            user_id,
            str(join_date),
            str(expiry_date),
            "free"
        )
    )

    conn.commit()

def is_subscription_active(user_id):
    cursor.execute(
        "SELECT expiry_date FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    if not result:
        return False

    expiry_date = datetime.fromisoformat(result[0])

    return datetime.now() <= expiry_date

def get_random_video():
    cursor.execute("SELECT file_id FROM videos")
    videos = cursor.fetchall()

    if not videos:
        return None

    return random.choice(videos)[0]

def payment_message(chat_id):

    text = """
💎 PREMIUM PLANS

• 1 Day = ₹3
• 1 Week = ₹19
• 1 Month = ₹45

💳 UPI ID:
<code>leeford1256@okicici</code>

After payment tap:
✅ I've Paid
"""

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ I've Paid",
            callback_data="paid"
        )
    )

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=markup
    )

def send_random_video(chat_id):

    video = get_random_video()

    if not video:
        bot.send_message(
            chat_id,
            "😕 No videos available right now."
        )
        return

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🎬 Another Video",
            callback_data="another_video"
        )
    )

    bot.send_video(
        chat_id,
        video,
        reply_markup=markup
    )

# =========================
# START COMMAND
# =========================

@bot.message_handler(commands=['start'])
def start(message):

    user_id = message.chat.id

    if not user_exists(user_id):
        add_user(user_id)

        welcome_text = """
🔥 Welcome to the Video Bot!

Use /start anytime to get random videos 🎬

Tap "Another Video" for more content.
"""

        bot.send_message(user_id, welcome_text)

    if is_subscription_active(user_id):
        send_random_video(user_id)
    else:
        payment_message(user_id)

# =========================
# ANOTHER VIDEO
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "another_video")
def another_video(call):

    send_random_video(call.message.chat.id)

# =========================
# PAYMENT CLAIM
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "paid")
def paid(call):

    user = call.from_user

    text = f"""
💰 New Payment Claim

👤 User ID: {user.id}
👤 Username: @{user.username}

Please verify payment manually.
"""

    try:
        bot.send_message(ADMIN_ID, text)

        bot.answer_callback_query(
            call.id,
            "Payment request sent to admin ✅"
        )

    except:
        bot.answer_callback_query(
            call.id,
            "Failed to notify admin ❌"
        )

# =========================
# SAVE VIDEOS (ADMIN ONLY)
# =========================

@bot.message_handler(content_types=['video'])
def save_video(message):

    if message.chat.id != ADMIN_ID:
        return

    file_id = message.video.file_id

    cursor.execute(
        "INSERT INTO videos (file_id) VALUES (?)",
        (file_id,)
    )

    conn.commit()

    bot.reply_to(
        message,
        "✅ Video saved successfully"
    )

# =========================
# BLOCK NORMAL USER MESSAGES
# =========================

@bot.message_handler(func=lambda message: True)
def block_messages(message):

    if message.chat.id == ADMIN_ID:
        return

    bot.reply_to(
        message,
        "❌ You can only use bot commands."
    )

# =========================
# RUN BOT
# =========================

print("✅ Bot Started Successfully")

bot.infinity_polling(skip_pending=True)

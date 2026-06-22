import telebot
import random
import sqlite3
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# TOKEN HERE
TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 8555836600

bot = telebot.TeleBot(TOKEN)

# DB
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    join_date TEXT,
    status TEXT,
    expiry TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    file_id TEXT
)
""")

conn.commit()

# GET USER
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

# RANDOM VIDEO
def get_random_video():
    cursor.execute("SELECT file_id FROM videos")
    videos = cursor.fetchall()

    if not videos:
        return None

    return random.choice(videos)[0]

# PAYMENT MESSAGE
def pay(message):
    text = """
💰 PREMIUM PLANS

1 Day = ₹3
1 Week = ₹19
1 Month = ₹45

UPI ID:
leeford1256@okicici

Send payment screenshot to admin for approval.
"""
    bot.send_message(message.chat.id, text)

# START COMMAND
@bot.message_handler(commands=['start'])
def start(message):

    user_id = message.chat.id
    user = get_user(user_id)

    if not user:

        join_date = datetime.now()
        expiry = join_date + timedelta(days=7)

        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                       (user_id, str(join_date), "free", str(expiry)))
        conn.commit()

        video = get_random_video()
        if video:
            bot.send_video(user_id, video)

        return

    expiry = datetime.fromisoformat(user[3])

    if datetime.now() <= expiry:

        video = get_random_video()
        if video:
            bot.send_video(user_id, video)

    else:
        pay(message)

# SAVE VIDEO (ADMIN OR CHANNEL)
@bot.message_handler(content_types=['video'])
def save_video(message):

    if message.chat.id == ADMIN_ID:

        file_id = message.video.file_id

        cursor.execute("INSERT INTO videos VALUES (?)", (file_id,))
        conn.commit()

        bot.reply_to(message, "Video saved ✅")

# ANOTHER VIDEO BUTTON
@bot.callback_query_handler(func=lambda call: call.data == "another_video")
def another_video(call):

    video = get_random_video()

    if video:
        bot.send_video(call.message.chat.id, video)

# BUTTONS
def get_video_buttons():
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton("🎬 Another Video", callback_data="another_video")
    )

    return markup

# POLLING
bot.polling()

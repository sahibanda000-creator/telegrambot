import os
import telebot
import random
import sqlite3
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

# Safe validation at startup
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable missing!")
if not ADMIN_ID_RAW:
    raise ValueError("❌ ADMIN_ID environment variable missing!")

ADMIN_ID = int(ADMIN_ID_RAW)

bot = telebot.TeleBot(TOKEN)

# =========================
# DATABASE
# =========================

def get_conn():
    conn = sqlite3.connect("bot.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_conn()
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
        (user_id, str(join_date), str(expiry_date), "free")
    )
    conn.commit()

def is_subscription_active(user_id):
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    expiry_date = datetime.fromisoformat(result[0])
    return datetime.now() <= expiry_date

def extend_subscription(user_id, days):
    """Admin use karega — subscription extend karta hai"""
    cursor.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        current_expiry = datetime.fromisoformat(result[0])
        # Agar already expire ho gaya to aaj se count karo
        base = max(current_expiry, datetime.now())
    else:
        base = datetime.now()
        cursor.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            (user_id, str(datetime.now()), str(base), "paid")
        )

    new_expiry = base + timedelta(days=days)
    cursor.execute(
        "UPDATE users SET expiry_date = ?, plan = ? WHERE user_id = ?",
        (str(new_expiry), "paid", user_id)
    )
    conn.commit()
    return new_expiry

def get_random_video():
    cursor.execute("SELECT file_id FROM videos")
    videos = cursor.fetchall()
    if not videos:
        return None
    return random.choice(videos)[0]

def payment_message(chat_id):
    text = """
💎 <b>PREMIUM PLANS</b>

• 1 Day  = ₹3
• 1 Week = ₹19
• 1 Month = ₹45

💳 <b>UPI ID:</b>
<code>leeford1256@okicici</code>

After payment tap ✅ I've Paid
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ I've Paid", callback_data="paid"))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

def send_random_video(chat_id):
    video = get_random_video()
    if not video:
        bot.send_message(chat_id, "😕 No videos available right now.")
        return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Another Video", callback_data="another_video"))
    bot.send_video(chat_id, video, reply_markup=markup)

# =========================
# START COMMAND
# =========================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not user_exists(user_id):
        add_user(user_id)
        bot.send_message(user_id, "🔥 <b>Welcome to the Video Bot!</b>\n\nTap below to get random videos 🎬", parse_mode="HTML")

    if is_subscription_active(user_id):
        send_random_video(user_id)
    else:
        payment_message(user_id)

# =========================
# ANOTHER VIDEO
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "another_video")
def another_video(call):
    if is_subscription_active(call.message.chat.id):
        send_random_video(call.message.chat.id)
    else:
        payment_message(call.message.chat.id)

# =========================
# PAYMENT CLAIM
# =========================

@bot.callback_query_handler(func=lambda call: call.data == "paid")
def paid(call):
    user = call.from_user
    text = f"""
💰 <b>New Payment Claim</b>

👤 User ID: <code>{user.id}</code>
👤 Username: @{user.username or "N/A"}

To activate, reply with:
/addplan {user.id} 1   (1 day)
/addplan {user.id} 7   (1 week)
/addplan {user.id} 30  (1 month)
"""
    try:
        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ Payment request sent to admin!")
    except Exception as e:
        print(f"Admin notify error: {e}")
        bot.answer_callback_query(call.id, "❌ Failed to notify admin.")

# =========================
# ADMIN: ACTIVATE PLAN
# =========================

@bot.message_handler(commands=['addplan'])
def addplan(message):
    if message.chat.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        bot.reply_to(message, "❌ Format: /addplan <user_id> <days>")
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        bot.reply_to(message, "❌ user_id aur days dono numbers hone chahiye.")
        return

    new_expiry = extend_subscription(target_id, days)

    bot.reply_to(message, f"✅ User {target_id} ka plan activate!\nExpiry: {new_expiry.strftime('%d %b %Y %H:%M')}")

    try:
        bot.send_message(target_id, f"🎉 <b>Your subscription is now active!</b>\n\nExpiry: {new_expiry.strftime('%d %b %Y')}", parse_mode="HTML")
    except:
        pass  # User ne bot block kiya hoga

# =========================
# ADMIN: STATS
# =========================

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.chat.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE expiry_date > ?", (str(datetime.now()),))
    active = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM videos")
    videos = cursor.fetchone()[0]

    bot.reply_to(message, f"📊 <b>Bot Stats</b>\n\n👥 Total Users: {total}\n✅ Active Subs: {active}\n🎬 Videos: {videos}", parse_mode="HTML")

# =========================
# SAVE VIDEOS (ADMIN ONLY)
# =========================

@bot.message_handler(content_types=['video'])
def save_video(message):
    if message.chat.id != ADMIN_ID:
        return
    file_id = message.video.file_id
    cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
    conn.commit()
    bot.reply_to(message, "✅ Video saved!")

# =========================
# BLOCK NORMAL MESSAGES
# =========================

@bot.message_handler(func=lambda message: True)
def block_messages(message):
    if message.chat.id == ADMIN_ID:
        return
    bot.reply_to(message, "❌ Use /start command.")

# =========================
# RUN
# =========================

print("✅ Bot Started Successfully")
bot.infinity_polling(skip_pending=True)

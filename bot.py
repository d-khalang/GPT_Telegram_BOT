from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import instaloader
import re
import asyncio
from parser import fetch_chatgpt_conversation
import os
from dotenv import load_dotenv

# Regex to extract shortcode from Instagram URL
INSTAGRAM_REGEX = r"(?:https?://)?(?:www\.)?instagram\.com/(?:reel|tv|p)/([a-zA-Z0-9_-]+)"
load_dotenv()

TOKEN = os.getenv('TOKEN')

# In-memory store: chat_id -> {'messages': [...], 'pos': int}
chat_progress = {}
BATCH_SIZE = 10

def split_message(text, max_length=4000):
    """Split long messages into chunks that fit Telegram's limit"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        # Find the last space within the limit
        split_point = text.rfind(' ', 0, max_length)
        if split_point == -1:
            split_point = max_length
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip()
    
    return chunks

# Initialize Instaloader
L = instaloader.Instaloader(download_videos=True, download_video_thumbnails=False,
                            download_comments=False, save_metadata=False, post_metadata_txt_pattern="")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = """Welcome! I'm a multi-functional bot with two main features:

📹 **Video Downloader**: Use `/video <Instagram link>` to fetch and send Instagram videos/reels

💬 **ChatGPT Share**: Use `/share <ChatGPT link>` to share ChatGPT conversations

Try either command to get started!"""
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def send_instagram_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /video <Instagram URL>")
        return

    text = " ".join(context.args)
    match = re.search(INSTAGRAM_REGEX, text)

    if not match:
        await update.message.reply_text("Please provide a valid Instagram video/reel/post link.")
        return

    shortcode = match.group(1)

    try:
        await update.message.reply_text("Processing...Just a moment.")
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if post.typename == 'GraphSidecar':
            count = 0
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    await update.message.reply_video(video=node.video_url)
                    count += 1
            if count == 0:
                await update.message.reply_text("No videos found in this carousel post.")
        elif post.is_video:
            await update.message.reply_video(video=post.video_url)
        else:
            await update.message.reply_text("This post does not contain a video.")

    except Exception as e:
        print("Error:", e)
        await update.message.reply_text("Failed to fetch the video. Maybe the post is private or invalid.")

async def send_next_batch(update, context, chat_id):
    data = chat_progress.get(chat_id)
    if not data:
        return
    messages = data['messages']
    pos = data['pos']
    end = min(pos + BATCH_SIZE, len(messages))
    for i in range(pos, end):
        msg = messages[i]
        role = "👤 *User:*" if msg["role"] == "user" else "🤖 *GPT:*"
        for chunk in split_message(msg['text']):
            await context.bot.send_message(chat_id=chat_id, text=f"{role}\n{chunk}", parse_mode=ParseMode.MARKDOWN)
            role = ""  # Only show the role label on the first chunk
            await asyncio.sleep(0.7)  # Add a delay between messages
    data['pos'] = end
    # If there are more messages, show the load more button
    if end < len(messages):
        keyboard = [[InlineKeyboardButton("Load more", callback_data="load_more")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text="_...message truncated. Click below to load more_", parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        # Optionally, notify that all messages are sent
        await context.bot.send_message(chat_id=chat_id, text="_End of conversation._", parse_mode=ParseMode.MARKDOWN)

async def load_more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    await send_next_batch(update, context, chat_id)

async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a ChatGPT share link.\nUsage: /share <ChatGPT URL>")
        return
    url = context.args[0]
    chat_id = update.effective_chat.id

    if "chat.openai.com" not in url and "chatgpt.com" not in url:
        await update.message.reply_text("Please send a valid ChatGPT conversation link.")
        return

    await update.message.reply_text("Fetching and parsing the ChatGPT conversation...")

    try:
        messages = await fetch_chatgpt_conversation(url)
    except Exception as e:
        await update.message.reply_text(f"Failed to fetch conversation: {e}")
        return

    if not messages:
        await update.message.reply_text("No messages found in the conversation.")
        return

    chat_progress[chat_id] = {'messages': messages, 'pos': 0}
    await update.message.reply_text("📩 *ChatGPT Conversation Shared:*", parse_mode=ParseMode.MARKDOWN)
    await send_next_batch(update, context, chat_id)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("video", send_instagram_video))
    app.add_handler(CommandHandler("share", share_command))
    app.add_handler(CallbackQueryHandler(load_more_callback, pattern="^load_more$"))

    print("Bot is running...")
    app.run_polling()


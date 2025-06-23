from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from dotenv import load_dotenv
import asyncio
import os
from parser import fetch_chatgpt_conversation

load_dotenv()

TOKEN = os.getenv('TOKEN')

# In-memory store: chat_id -> {'messages': [...], 'pos': int}
chat_progress = {}
BATCH_SIZE = 10

def split_message(text, max_length=4000):
    # Split by paragraphs first for better readability
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += '\n' + para
            else:
                current_chunk = para
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send me a ChatGPT link and I'll summarize it here.")

async def handle_chatgpt_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
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
        await update.message.reply_text("Please provide a ChatGPT share link.")
        return
    url = context.args[0]
    


app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_chatgpt_link))
app.add_handler(CallbackQueryHandler(load_more_callback, pattern="^load_more$"))
app.add_handler(CommandHandler("share", share_command))

app.run_polling()

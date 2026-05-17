import os
import re
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("8816935387:AAGQZt0s_TmF4XIYaTTM8euuu_rhI4yoo3s")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN is not set in environment variables")

# تنظیمات سرعت
MAX_WORKERS = 5
REQUEST_TIMEOUT = 8
DELAY_BETWEEN_REQUESTS = 0.1

WAITING_FOR_USERNAMES = 1
RESULT_FOLDER = "telegram_results"
if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ ربات چکر سریع یوزرنیم تلگرام\n\n"
        "📋 لیست یوزرنیم‌ها رو بفرست (با @ یا بدون @)\n"
        "هر خط یکی یا با کاما جدا کن.\n\n"
        "🚀 ربات با سرعت بالا همه رو یکجا چک میکنه."
    )
    return WAITING_FOR_USERNAMES

def check_username_fast(username):
    try:
        url = f"https://t.me/{username}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers, allow_redirects=True)
        if "If you have Telegram, you can contact" in response.text:
            return ("available", username)
        else:
            return ("taken", username)
    except:
        return ("error", username)

def check_usernames_batch(usernames, progress_callback=None):
    results = {"available": [], "taken": [], "error": []}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_username_fast, u): u for u in usernames}
        for i, future in enumerate(as_completed(futures)):
            status, username = future.result()
            if status == "available":
                results["available"].append(username)
            else:
                results["taken"].append(username)
            if progress_callback:
                progress_callback(i + 1, len(usernames), len(results["available"]))
            time.sleep(DELAY_BETWEEN_REQUESTS)
    return results

async def check_usernames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    status_msg = await update.message.reply_text("⚡ در حال آماده‌سازی لیست...")

    if ',' in text:
        raw_list = [u.strip() for u in text.split(',')]
    else:
        raw_list = [u.strip() for u in text.split('\n')]

    usernames = []
    for item in raw_list:
        if item:
            clean = re.sub(r'^@+', '', item).strip()
            if clean and len(clean) >= 5:
                usernames.append(clean)

    usernames = list(dict.fromkeys(usernames))

    if not usernames:
        await status_msg.edit_text("❌ لیست خالی یا کمتر از ۵ حرف بود.")
        return WAITING_FOR_USERNAMES

    await status_msg.edit_text(f"⚡ در حال بررسی همزمان {len(usernames)} یوزرنیم با {MAX_WORKERS} نخ همزمان...")

    def update_progress(current, total, available_count):
        if current % max(1, total // 10) == 0 or current == total:
            asyncio.create_task(status_msg.edit_text(
                f"⚡ بررسی... {current}/{total}\n✅ {available_count} آزاد تا الان"
            ))

    start_time = time.time()
    results = check_usernames_batch(usernames, update_progress)
    elapsed_time = time.time() - start_time

    await status_msg.delete()

    result_file = os.path.join(RESULT_FOLDER, f"result_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write(f"نتایج چک یوزرنیم\nزمان: {datetime.now()}\nزمان اجرا: {elapsed_time:.2f} ثانیه\n")
        f.write(f"کل: {len(usernames)} | آزاد: {len(results['available'])} | گرفته: {len(results['taken'])}\n\n")
        f.write("آزادها:\n")
        for u in results['available']:
            f.write(f"@{u}\n")
        if results['taken']:
            f.write("\nگرفته شده‌ها:\n")
            for u in results['taken']:
                f.write(f"@{u}\n")

    summary = f"⚡ **نتیجه چک**\n⏱️ {elapsed_time:.1f} ثانیه | 🔢 {len(usernames)} عدد\n✅ آزاد: {len(results['available'])} | ❌ گرفته: {len(results['taken'])}\n\n"

    if results['available']:
        summary += "**✅ آزادها:**\n"
        for u in results['available'][:25]:
            summary += f"`@{u}`\n"
        if len(results['available']) > 25:
            summary += f"\n... و {len(results['available'])-25} تای دیگر توی فایل"
    else:
        summary += "❌ هیچ یوزرنیم آزادی پیدا نشد."

    await update.message.reply_text(summary, parse_mode='Markdown')

    with open(result_file, 'rb') as f:
        await update.message.reply_document(f, filename=os.path.basename(result_file))

    await update.message.reply_text("🔄 برای چک جدید /start رو بزن.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ لغو شد.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAITING_FOR_USERNAMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_usernames)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    print("🤖 ربات روشن شد...")
    application.run_polling()

if __name__ == "__main__":
    main()

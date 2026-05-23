import os
import logging
import aiofiles
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
import storage
import ai
import api
api.start_api_thread()

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # твой Telegram ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    storage.get_user(update.effective_chat.id)
    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"Я твой фитнес-ассистент. Вот что я умею:\n\n"
        f"🎤 Голосовое или ✏️ текст — запишу что съел\n"
        f"📸 Фото еды — посчитаю калории\n"
        f"💧 /water — записать воду\n"
        f"📊 /stats — статистика за день\n"
        f"📅 /history — история за 7 дней\n"
        f"⚖️ /bmi — рассчитать ИМТ и норму калорий\n"
        f"💡 /advice — совет что ещё съесть\n"
        f"❓ /ask — задать вопрос тренеру\n"
        f"🔄 /reset — сбросить данные за день\n"
    )
    # Кнопка мини-приложения
    keyboard = [[
        InlineKeyboardButton(
            "💪 Открыть FitBot App",
            web_app=WebAppInfo(url="https://ceprazovnikita.github.io/fitness-bot-app/")
        )
    ]]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚖️ Введи свой вес и рост через пробел\n\nПример: `75 178`",
        parse_mode="Markdown",
    )
    context.user_data["waiting_bmi"] = True


async def water_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💧 Сколько воды выпил? Введи количество в мл\n\nПример: `250`",
        parse_mode="Markdown",
    )
    context.user_data["waiting_water"] = True


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = storage.get_user(chat_id)
    meals = user.get("meals_today", [])
    calories_today = user.get("calories_today", 0)
    calories_target = user.get("calories_target", 2000)
    water_today = user.get("water_today", 0)

    total_proteins = sum(m.get("proteins", 0) for m in meals)
    total_fats = sum(m.get("fats", 0) for m in meals)
    total_carbs = sum(m.get("carbs", 0) for m in meals)

    if not meals:
        await update.message.reply_text("📭 Сегодня ты ещё ничего не записал.")
        return

    meals_text = "\n".join(
        [f"• {m['meal']} — {m['calories']} ккал" for m in meals]
    )
    remaining = calories_target - calories_today
    emoji = "✅" if remaining >= 0 else "⚠️"
    water_emoji = "✅" if water_today >= 2000 else "💧"

    text = (
        f"📊 *Статистика за сегодня:*\n\n"
        f"{meals_text}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🔥 Съедено: *{calories_today}* ккал\n"
        f"🎯 Норма: *{calories_target}* ккал\n"
        f"{emoji} Остаток: *{remaining}* ккал\n\n"
        f"🥩 Белки: *{total_proteins}* г\n"
        f"🧈 Жиры: *{total_fats}* г\n"
        f"🍞 Углеводы: *{total_carbs}* г\n\n"
        f"{water_emoji} Вода: *{water_today}* мл из 2000 мл"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = storage.get_user(chat_id)
    history = user.get("history", [])

    if not history:
        await update.message.reply_text("📭 История пока пуста — начни записывать питание!")
        return

    text = "📅 *История за последние дни:*\n\n"
    for day in reversed(history[-7:]):
        text += (
            f"📆 *{day['date']}*\n"
            f"🔥 Калории: {day['calories']} ккал\n"
            f"💧 Вода: {day['water']} мл\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def advice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = storage.get_user(chat_id)
    meals = user.get("meals_today", [])
    calories_today = user.get("calories_today", 0)
    calories_target = user.get("calories_target", 2000)

    await update.message.reply_text("💭 Анализирую твой рацион...")
    advice = ai.get_daily_advice(meals, calories_today, calories_target)
    await update.message.reply_text(f"💡 *Совет от диетолога:*\n\n{advice}", parse_mode="Markdown")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Напиши свой вопрос — я передам его тренеру и он ответит тебе анонимно.",
    )
    context.user_data["waiting_question"] = True


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.reset_today(update.effective_chat.id)
    await update.message.reply_text("🔄 Данные за сегодня сброшены!")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Ответ тренера пользователю
    if context.user_data.get("waiting_answer") and str(chat_id) == str(ADMIN_ID):
        target_id = context.user_data.get("answer_to")
        if target_id:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💬 *Ответ тренера:*\n\n{text}",
                parse_mode="Markdown",
            )
            await update.message.reply_text("✅ Ответ отправлен!")
            context.user_data["waiting_answer"] = False
            context.user_data["answer_to"] = None
        return

    # Вопрос тренеру
    if context.user_data.get("waiting_question"):
        if ADMIN_ID:
            keyboard = [[InlineKeyboardButton("Ответить", callback_data=f"answer_{chat_id}")]]
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❓ *Вопрос от пользователя:*\n\n{text}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        await update.message.reply_text("✅ Вопрос отправлен тренеру! Ожидай ответа.")
        context.user_data["waiting_question"] = False
        return

    # Ввод веса и роста
    if context.user_data.get("waiting_bmi"):
        try:
            parts = text.split()
            weight = float(parts[0])
            height = float(parts[1])
            result = ai.calculate_bmi(weight, height)
            storage.update_user(chat_id, {
                "weight": weight,
                "height": height,
                "calories_target": result["calories_target"],
            })
            context.user_data["waiting_bmi"] = False
            reply = (
                f"📊 *Твои показатели:*\n\n"
                f"⚖️ ИМТ: *{result['bmi']}*\n"
                f"📋 Категория: *{result['category']}*\n"
                f"🔥 Норма калорий: *{result['calories_target']}* ккал/день\n\n"
                f"Теперь я буду учитывать твою норму в статистике!"
            )
            await update.message.reply_text(reply, parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Неверный формат. Пример: `75 178`", parse_mode="Markdown")
        return

    # Ввод воды
    if context.user_data.get("waiting_water"):
        try:
            ml = int(text)
            storage.add_water(chat_id, ml)
            user = storage.get_user(chat_id)
            water_today = user.get("water_today", 0)
            context.user_data["waiting_water"] = False
            emoji = "✅" if water_today >= 2000 else "💧"
            await update.message.reply_text(
                f"💧 Записал *{ml}* мл\n\n{emoji} Всего сегодня: *{water_today}* мл из 2000 мл",
                parse_mode="Markdown",
            )
        except:
            await update.message.reply_text("❌ Введи число. Пример: `250`", parse_mode="Markdown")
        return

    # Анализ еды
    await update.message.reply_text("🔍 Считаю калории...")
    try:
        result = ai.analyze_calories(text)
        storage.add_meal(chat_id, result["description"], result["calories"],
                        result.get("proteins", 0), result.get("fats", 0), result.get("carbs", 0))
        user = storage.get_user(chat_id)
        calories_today = user.get("calories_today", 0)
        calories_target = user.get("calories_target", 2000)
        remaining = calories_target - calories_today

        reply = (
            f"✅ *{result['description']}*\n\n"
            f"🔥 Калории: *{result['calories']}* ккал\n"
            f"🥩 Белки: {result.get('proteins', '?')} г\n"
            f"🧈 Жиры: {result.get('fats', '?')} г\n"
            f"🍞 Углеводы: {result.get('carbs', '?')} г\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 За сегодня: *{calories_today}* / *{calories_target}* ккал\n"
            f"💚 Остаток: *{remaining}* ккал"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Ошибка анализа: {e}")
        await update.message.reply_text("❌ Не смог распознать еду. Попробуй описать подробнее.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("📸 Анализирую фото...")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_path = f"photo_{chat_id}.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(file.file_path) as resp:
                async with aiofiles.open(image_path, "wb") as f:
                    await f.write(await resp.read())

        result = ai.analyze_calories_from_photo(image_path)
        os.remove(image_path)

        storage.add_meal(chat_id, result["description"], result["calories"],
                        result.get("proteins", 0), result.get("fats", 0), result.get("carbs", 0))
        user = storage.get_user(chat_id)
        calories_today = user.get("calories_today", 0)
        calories_target = user.get("calories_target", 2000)
        remaining = calories_target - calories_today

        reply = (
            f"✅ *{result['description']}*\n\n"
            f"🔥 Калории: *{result['calories']}* ккал\n"
            f"🥩 Белки: {result.get('proteins', '?')} г\n"
            f"🧈 Жиры: {result.get('fats', '?')} г\n"
            f"🍞 Углеводы: {result.get('carbs', '?')} г\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 За сегодня: *{calories_today}* / *{calories_target}* ккал\n"
            f"💚 Остаток: *{remaining}* ккал"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        log.error(f"Ошибка фото: {e}")
        await update.message.reply_text("❌ Не смог распознать еду на фото. Попробуй другое фото.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("🎤 Распознаю голосовое...")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        audio_path = f"voice_{chat_id}.ogg"

        async with aiohttp.ClientSession() as session:
            async with session.get(file.file_path) as resp:
                async with aiofiles.open(audio_path, "wb") as f:
                    await f.write(await resp.read())

        text = ai.transcribe_audio(audio_path)
        os.remove(audio_path)

        await update.message.reply_text(f"📝 Распознал: _{text}_\n\n🔍 Считаю калории...", parse_mode="Markdown")

        result = ai.analyze_calories(text)
        storage.add_meal(chat_id, result["description"], result["calories"],
                        result.get("proteins", 0), result.get("fats", 0), result.get("carbs", 0))
        user = storage.get_user(chat_id)
        calories_today = user.get("calories_today", 0)
        calories_target = user.get("calories_target", 2000)
        remaining = calories_target - calories_today

        reply = (
            f"✅ *{result['description']}*\n\n"
            f"🔥 Калории: *{result['calories']}* ккал\n"
            f"🥩 Белки: {result.get('proteins', '?')} г\n"
            f"🧈 Жиры: {result.get('fats', '?')} г\n"
            f"🍞 Углеводы: {result.get('carbs', '?')} г\n\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📊 За сегодня: *{calories_today}* / *{calories_target}* ккал\n"
            f"💚 Остаток: *{remaining}* ккал"
        )
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        log.error(f"Ошибка голосового: {e}")
        await update.message.reply_text("❌ Не смог обработать голосовое. Попробуй ещё раз.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("answer_"):
        user_id = int(query.data.split("_")[1])
        context.user_data["waiting_answer"] = True
        context.user_data["answer_to"] = user_id
        await query.message.reply_text("✏️ Напиши ответ пользователю:")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bmi", bmi_command))
    app.add_handler(CommandHandler("water", water_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("advice", advice_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    log.info("Фитнес-бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
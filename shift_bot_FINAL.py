import logging
import json
import os
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файл для хранения графика
SCHEDULE_FILE = 'schedule.json'

# Состояния для ConversationHandler
CHOOSING_DATE, CHOOSING_SHIFT, CHOOSING_AUTO_DATE, CHOOSING_AUTO_SHIFT = range(4)

# Типы смен
SHIFT_TYPES = {
    'day': {'name': 'Дневная смена', 'emoji': '☕'},
    'night': {'name': 'Ночная смена', 'emoji': '🌙'},
    'rest': {'name': 'Отсыпной', 'emoji': '😴'},
    'dayoff': {'name': 'Выходной', 'emoji': '🎉'}
}

# Цикл смен
SHIFT_CYCLE = ['day', 'night', 'rest', 'dayoff']

def load_schedule():
    """Загрузка графика из файла"""
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_schedule(schedule):
    """Сохранение графика в файл"""
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

def generate_auto_schedule(start_date_str, start_shift_type, days=365):
    """Генерация графика на year вперёд по циклу"""
    schedule = {}
    start_date = datetime.strptime(start_date_str, '%d.%m.%Y')
    
    # Находим позицию начальной смены в цикле
    current_shift_index = SHIFT_CYCLE.index(start_shift_type)
    
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%d.%m.%Y')
        
        # Берём текущую смену из цикла
        shift_type = SHIFT_CYCLE[current_shift_index % len(SHIFT_CYCLE)]
        schedule[date_str] = shift_type
        
        current_shift_index += 1
    
    return schedule

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [KeyboardButton("📅 Добавить смену")],
        [KeyboardButton("🤖 Автозаполнение графика")],
        [KeyboardButton("📋 Мой график")],
        [KeyboardButton("🗑 Удалить смену")],
        [KeyboardButton("🗑 Очистить весь график")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "👋 Привет! Я помогу тебе отслеживать график смен.\n\n"
        "🔔 Каждый день в 20:05 буду напоминать о завтрашней смене!\n\n"
        "🤖 Используй 'Автозаполнение графика' чтобы заполнить весь год автоматически!\n\n"
        "Выбери действие:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 <b>Доступные команды:</b>\n\n"
        "📅 <b>Добавить смену</b> - добавить одну дату вручную\n"
        "🤖 <b>Автозаполнение графика</b> - заполнить весь год автоматически\n"
        "   (просто укажи начальную дату и тип смены)\n"
        "📋 <b>Мой график</b> - посмотреть все смены\n"
        "🗑 <b>Удалить смену</b> - удалить конкретную дату\n"
        "🗑 <b>Очистить весь график</b> - удалить все смены\n\n"
        "<b>Цикл смен:</b>\n"
        "☕ День → 🌙 Ночь → 😴 Отсыпной → 🎉 Выходной\n\n"
        "⏰ Напоминания приходят каждый день в 20:05"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def auto_schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало автозаполнения графика"""
    await update.message.reply_text(
        "🤖 <b>Автозаполнение графика на год</b>\n\n"
        "Укажи дату начала в формате ДД.ММ.ГГГГ\n"
        "Например: 16.01.2026\n\n"
        "Или напиши 'отмена' для выхода",
        parse_mode='HTML'
    )
    return CHOOSING_AUTO_DATE

async def auto_schedule_receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение начальной даты для автозаполнения"""
    text = update.message.text.strip()
    
    if text.lower() == 'отмена':
        keyboard = [
            [KeyboardButton("📅 Добавить смену")],
            [KeyboardButton("🤖 Автозаполнение графика")],
            [KeyboardButton("📋 Мой график")],
            [KeyboardButton("🗑 Удалить смену")],
            [KeyboardButton("🗑 Очистить весь график")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ Автозаполнение отменено", reply_markup=reply_markup)
        return ConversationHandler.END
    
    try:
        # Проверяем формат даты
        date_obj = datetime.strptime(text, '%d.%m.%Y')
        context.user_data['auto_start_date'] = text
        
        # Кнопки для выбора начальной смены
        keyboard = [
            [KeyboardButton("☕ Дневная смена")],
            [KeyboardButton("🌙 Ночная смена")],
            [KeyboardButton("😴 Отсыпной")],
            [KeyboardButton("🎉 Выходной")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ Начальная дата: {text}\n\n"
            "Теперь выбери с какой смены начать цикл:\n\n"
            "Цикл будет: День → Ночь → Отсыпной → Выходной",
            reply_markup=reply_markup
        )
        return CHOOSING_AUTO_SHIFT
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты!\n"
            "Используй формат: ДД.ММ.ГГГГ (например, 16.01.2026)"
        )
        return CHOOSING_AUTO_DATE

async def auto_schedule_receive_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение начальной смены и генерация графика"""
    text = update.message.text.strip()
    
    if text == "❌ Отмена":
        keyboard = [
            [KeyboardButton("📅 Добавить смену")],
            [KeyboardButton("🤖 Автозаполнение графика")],
            [KeyboardButton("📋 Мой график")],
            [KeyboardButton("🗑 Удалить смену")],
            [KeyboardButton("🗑 Очистить весь график")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ Автозаполнение отменено", reply_markup=reply_markup)
        return ConversationHandler.END
    
    # Определяем тип смены
    shift_type = None
    if "☕" in text or "дневная" in text.lower():
        shift_type = 'day'
    elif "🌙" in text or "ночная" in text.lower():
        shift_type = 'night'
    elif "😴" in text or "отсыпной" in text.lower():
        shift_type = 'rest'
    elif "🎉" in text or "выходной" in text.lower():
        shift_type = 'dayoff'
    
    if shift_type:
        start_date = context.user_data['auto_start_date']
        user_id = str(update.effective_user.id)
        
        await update.message.reply_text("⏳ Генерирую график на год...")
        
        # Генерируем график на 365 дней
        auto_schedule = generate_auto_schedule(start_date, shift_type, days=365)
        
        # Загружаем существующий график
        schedule = load_schedule()
        if user_id not in schedule:
            schedule[user_id] = {}
        
        # Добавляем автоматически сгенерированный график
        schedule[user_id].update(auto_schedule)
        save_schedule(schedule)
        
        shift_info = SHIFT_TYPES[shift_type]
        
        # Возвращаем основную клавиатуру
        keyboard = [
            [KeyboardButton("📅 Добавить смену")],
            [KeyboardButton("🤖 Автозаполнение графика")],
            [KeyboardButton("📋 Мой график")],
            [KeyboardButton("🗑 Удалить смену")],
            [KeyboardButton("🗑 Очистить весь график")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Показываем первые несколько дней для примера
        preview = []
        start_date_obj = datetime.strptime(start_date, '%d.%m.%Y')
        for i in range(8):  # Показываем первые 8 дней (2 цикла)
            date = start_date_obj + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            shift = auto_schedule[date_str]
            shift_info_preview = SHIFT_TYPES[shift]
            preview.append(f"{shift_info_preview['emoji']} {date_str} - {shift_info_preview['name']}")
        
        preview_text = "\n".join(preview)
        
        await update.message.reply_text(
            f"✅ График на год заполнен автоматически!\n\n"
            f"📅 Начало: {start_date}\n"
            f"📊 Добавлено смен: 365\n\n"
            f"<b>Первые 8 дней:</b>\n{preview_text}\n\n"
            f"Используй 'Мой график' чтобы посмотреть все смены",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Неверный выбор! Выбери тип смены из кнопок.")
        return CHOOSING_AUTO_SHIFT

async def add_shift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления смены"""
    await update.message.reply_text(
        "📅 Введи дату в формате ДД.ММ.ГГГГ\n"
        "Например: 18.01.2026\n\n"
        "Или напиши 'отмена' для выхода"
    )
    return CHOOSING_DATE

async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты от пользователя"""
    text = update.message.text.strip()
    
    if text.lower() == 'отмена':
        await update.message.reply_text("❌ Добавление смены отменено")
        return ConversationHandler.END
    
    try:
        # Проверяем формат даты
        date_obj = datetime.strptime(text, '%d.%m.%Y')
        context.user_data['selected_date'] = text
        
        # Кнопки для выбора типа смены
        keyboard = [
            [KeyboardButton("☕ Дневная смена")],
            [KeyboardButton("🌙 Ночная смена")],
            [KeyboardButton("😴 Отсыпной")],
            [KeyboardButton("🎉 Выходной")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ Дата: {text}\n\n"
            "Теперь выбери тип смены:",
            reply_markup=reply_markup
        )
        return CHOOSING_SHIFT
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты!\n"
            "Используй формат: ДД.ММ.ГГГГ (например, 18.01.2026)"
        )
        return CHOOSING_DATE

async def receive_shift_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение типа смены от пользователя"""
    text = update.message.text.strip()
    
    if text == "❌ Отмена":
        # Возвращаем основную клавиатуру
        keyboard = [
            [KeyboardButton("📅 Добавить смену")],
            [KeyboardButton("🤖 Автозаполнение графика")],
            [KeyboardButton("📋 Мой график")],
            [KeyboardButton("🗑 Удалить смену")],
            [KeyboardButton("🗑 Очистить весь график")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ Добавление смены отменено", reply_markup=reply_markup)
        return ConversationHandler.END
    
    # Определяем тип смены
    shift_type = None
    if "☕" in text or "дневная" in text.lower():
        shift_type = 'day'
    elif "🌙" in text or "ночная" in text.lower():
        shift_type = 'night'
    elif "😴" in text or "отсыпной" in text.lower():
        shift_type = 'rest'
    elif "🎉" in text or "выходной" in text.lower():
        shift_type = 'dayoff'
    
    if shift_type:
        date_str = context.user_data['selected_date']
        user_id = str(update.effective_user.id)
        
        # Загружаем график
        schedule = load_schedule()
        if user_id not in schedule:
            schedule[user_id] = {}
        
        # Добавляем смену
        schedule[user_id][date_str] = shift_type
        save_schedule(schedule)
        
        shift_info = SHIFT_TYPES[shift_type]
        
        # Возвращаем основную клавиатуру
        keyboard = [
            [KeyboardButton("📅 Добавить смену")],
            [KeyboardButton("🤖 Автозаполнение графика")],
            [KeyboardButton("📋 Мой график")],
            [KeyboardButton("🗑 Удалить смену")],
            [KeyboardButton("🗑 Очистить весь график")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ Смена добавлена!\n\n"
            f"📅 Дата: {date_str}\n"
            f"{shift_info['emoji']} Тип: {shift_info['name']}",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Неверный выбор! Выбери тип смены из кнопок.")
        return CHOOSING_SHIFT

async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать график смен"""
    user_id = str(update.effective_user.id)
    schedule = load_schedule()
    
    if user_id not in schedule or not schedule[user_id]:
        await update.message.reply_text("📋 У тебя пока нет запланированных смен.\n\nИспользуй:\n🤖 'Автозаполнение графика' - для автоматического заполнения\n📅 'Добавить смену' - для ручного добавления")
        return
    
    user_schedule = schedule[user_id]
    
    # Сортируем даты
    sorted_dates = sorted(user_schedule.keys(), key=lambda x: datetime.strptime(x, '%d.%m.%Y'))
    
    # Показываем ближайшие 30 смен
    today = datetime.now()
    future_dates = [d for d in sorted_dates if datetime.strptime(d, '%d.%m.%Y') >= today][:30]
    
    if not future_dates:
        await update.message.reply_text("📋 У тебя нет будущих смен в графике.")
        return
    
    message = "📋 <b>Твой график смен (ближайшие 30 дней):</b>\n\n"
    
    for date_str in future_dates:
        shift_type = user_schedule[date_str]
        shift_info = SHIFT_TYPES[shift_type]
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        weekday = date_obj.strftime('%A')
        weekday_ru = {
            'Monday': 'Пн',
            'Tuesday': 'Вт',
            'Wednesday': 'Ср',
            'Thursday': 'Чт',
            'Friday': 'Пт',
            'Saturday': 'Сб',
            'Sunday': 'Вс'
        }.get(weekday, weekday)
        
        # Отмечаем сегодня и завтра
        if date_obj.date() == today.date():
            marker = " 👈 СЕГОДНЯ"
        elif date_obj.date() == (today + timedelta(days=1)).date():
            marker = " 👉 ЗАВТРА"
        else:
            marker = ""
        
        message += f"{shift_info['emoji']} <b>{date_str}</b> ({weekday_ru}){marker}\n"
    
    total_count = len(sorted_dates)
    message += f"\n📊 Всего смен в графике: {total_count}"
    
    await update.message.reply_text(message, parse_mode='HTML')

async def delete_shift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления смены"""
    user_id = str(update.effective_user.id)
    schedule = load_schedule()
    
    if user_id not in schedule or not schedule[user_id]:
        await update.message.reply_text("📋 У тебя нет запланированных смен для удаления")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🗑 Введи дату смены для удаления в формате ДД.ММ.ГГГГ\n"
        "Например: 18.01.2026\n\n"
        "Или напиши 'отмена' для выхода"
    )
    return CHOOSING_DATE

async def delete_shift_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления смены"""
    text = update.message.text.strip()
    
    if text.lower() == 'отмена':
        await update.message.reply_text("❌ Удаление отменено")
        return ConversationHandler.END
    
    try:
        # Проверяем формат даты
        datetime.strptime(text, '%d.%m.%Y')
        
        user_id = str(update.effective_user.id)
        schedule = load_schedule()
        
        if user_id in schedule and text in schedule[user_id]:
            del schedule[user_id][text]
            save_schedule(schedule)
            await update.message.reply_text(f"✅ Смена на {text} удалена!")
        else:
            await update.message.reply_text(f"❌ Смена на {text} не найдена в графике")
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты!\n"
            "Используй формат: ДД.ММ.ГГГГ (например, 18.01.2026)"
        )
        return CHOOSING_DATE

async def clear_all_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить весь график"""
    user_id = str(update.effective_user.id)
    schedule = load_schedule()
    
    if user_id in schedule and schedule[user_id]:
        count = len(schedule[user_id])
        schedule[user_id] = {}
        save_schedule(schedule)
        await update.message.reply_text(f"✅ Весь график очищен! Удалено смен: {count}")
    else:
        await update.message.reply_text("📋 У тебя нет смен для удаления")

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневное напоминание в 20:05"""
    schedule = load_schedule()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    for user_id, user_schedule in schedule.items():
        if tomorrow in user_schedule:
            shift_type = user_schedule[tomorrow]
            shift_info = SHIFT_TYPES[shift_type]
            
            message = f"{shift_info['emoji']} Завтра {shift_info['name'].lower()}!"
            
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=message
                )
            except Exception as e:
                logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    keyboard = [
        [KeyboardButton("📅 Добавить смену")],
        [KeyboardButton("🤖 Автозаполнение графика")],
        [KeyboardButton("📋 Мой график")],
        [KeyboardButton("🗑 Удалить смену")],
        [KeyboardButton("🗑 Очистить весь график")],
        [KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("❌ Операция отменена", reply_markup=reply_markup)
    return ConversationHandler.END

def main():
    """Запуск бота"""
    # Получаем токен из переменной окружения или используем значение по умолчанию
    TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    
    if TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("⚠️ ВНИМАНИЕ: Токен не установлен!")
        print("Установи переменную окружения TELEGRAM_TOKEN или измени код")
        return
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Обработчик автозаполнения графика
    auto_schedule_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🤖 Автозаполнение графика"), auto_schedule_start)
        ],
        states={
            CHOOSING_AUTO_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, auto_schedule_receive_date)],
            CHOOSING_AUTO_SHIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, auto_schedule_receive_shift)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="auto_schedule",
        persistent=False
    )
    
    # Обработчик добавления смены
    add_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("📅 Добавить смену"), add_shift_start)
        ],
        states={
            CHOOSING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date)],
            CHOOSING_SHIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_shift_type)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="add_shift",
        persistent=False
    )
    
    # Обработчик удаления смены
    delete_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🗑 Удалить смену"), delete_shift_start)
        ],
        states={
            CHOOSING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_shift_confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name="delete_shift",
        persistent=False
    )
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(auto_schedule_handler)
    application.add_handler(add_conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(MessageHandler(filters.Regex("📋 Мой график"), show_schedule))
    application.add_handler(MessageHandler(filters.Regex("🗑 Очистить весь график"), clear_all_schedule))
    application.add_handler(MessageHandler(filters.Regex("ℹ️ Помощь"), help_command))
    
    # Настройка ежедневного напоминания в 20:05
    job_queue = application.job_queue
    
    if job_queue is not None:
        # Время напоминания: 20:05 (по времени сервера)
        # Для Render (UTC) и Украины (UTC+2/UTC+3), установи 18:05 для зимы
        reminder_time = time(hour=18, minute=5, second=0)  # 18:05 UTC = 20:05 Киев (зима)
        
        job_queue.run_daily(
            send_daily_reminder,
            time=reminder_time,
            days=(0, 1, 2, 3, 4, 5, 6)  # Каждый день недели
        )
        print("⏰ Напоминания настроены на 20:05 по Киеву (18:05 UTC)")
    else:
        print("⚠️ ВНИМАНИЕ: JobQueue не доступен!")
        print("📝 Выполни команду: pip install \"python-telegram-bot[job-queue]\"")
        print("🔄 После установки перезапусти бота")
    
    # Запуск бота
    print("🤖 Бот запущен и работает!")
    print("🤖 Используй 'Автозаполнение графика' для быстрого заполнения!")
    print("📱 Найди своего бота в Telegram и нажми /start")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

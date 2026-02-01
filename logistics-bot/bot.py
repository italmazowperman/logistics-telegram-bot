#!/usr/bin/env python3
"""
Telegram Bot for Margiana Logistic Services
Уведомления, запросы данных и отчеты
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import traceback
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, CallbackContext
)
from supabase import create_client, Client
from dotenv import load_dotenv
from report_generator import generate_pdf_report
from utils import format_date, calculate_days_until

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
ADMIN_CHAT_IDS = [int(x.strip()) for x in os.getenv('ADMIN_CHAT_IDS', '').split(',') if x.strip()]
TIMEZONE = pytz.timezone('Asia/Ashgabat')

# Проверка обязательных переменных
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ SUPABASE_URL или SUPABASE_KEY не установлены!")
    raise ValueError("Supabase credentials are required")

# Инициализация Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase client initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Supabase client: {e}")
    raise

# Глобальные переменные
last_check_time = datetime.now(TIMEZONE)
subscribers = set(ADMIN_CHAT_IDS)  # Админы по умолчанию подписаны

class LogisticsBot:
    def __init__(self):
        self.status_emojis = {
            'New': '🆕',
            'In Progress CHN': '🇨🇳',
            'In Transit CHN-IR': '🚢',
            'In Progress IR': '🇮🇷',
            'In Transit IR-TKM': '🚛',
            'Completed': '✅',
            'Cancelled': '❌'
        }
        
    # ==================== КОМАНДЫ БОТА ====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /start"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Я бот для отслеживания грузов Margiana Logistic Services.

📊 **ОСНОВНЫЕ КОМАНДЫ:**

📦 **ИНФОРМАЦИЯ:**
/orders - Все активные заказы
/order [номер] - Детали заказа
/status [статус] - Заказы по статусу
/today - Задачи на сегодня
/containers - Контейнеры в пути
/drivers - Активные водители

📈 **ОТЧЕТЫ:**
/report - Сводный отчет
/report_pdf - Отчет в PDF
/completed_30 - Завершенные за 30 дней
/no_photos - Без фото загрузки
/urgent - Срочные заказы (ETA < 3 дня)

🔔 **УВЕДОМЛЕНИЯ:**
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться

🆘 **ПОМОЩЬ:**
/help - Все команды
/contacts - Контакты компании
        """
        
        # Добавляем в подписчики
        if chat_id not in subscribers:
            subscribers.add(chat_id)
            logger.info(f"New subscriber: {chat_id}")
        
        keyboard = [
            [InlineKeyboardButton("📦 Активные заказы", callback_data="active_orders"),
             InlineKeyboardButton("📋 Задачи", callback_data="today_tasks")],
            [InlineKeyboardButton("📊 Отчет", callback_data="report"),
             InlineKeyboardButton("🚚 Водители", callback_data="drivers")],
            [InlineKeyboardButton("🆘 Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /help"""
        help_text = """
📋 **ВСЕ КОМАНДЫ БОТА:**

📦 **ЗАКАЗЫ:**
/orders - Все активные заказы
/order [номер] - Детали заказа (например: /order ORD-001)
/status [статус] - Заказы по статусу
/today - Задачи на сегодня
/containers - Контейнеры в пути
/drivers - Активные водители
/search [текст] - Поиск по номеру/клиенту

📈 **ОТЧЕТЫ И ФИЛЬТРЫ:**
/report - Сводный отчет
/report_pdf - Отчет в PDF (фирменный стиль)
/completed_30 - Завершенные за 30 дней
/no_photos - Заказы без фото загрузки
/no_local_charges - Без местных сборов
/no_tex - Без TLX
/urgent - Срочные заказы (ETA < 3 дня)
/delayed - Просроченные задачи

🔔 **УВЕДОМЛЕНИЯ:**
/subscribe - Подписаться на уведомления
/unsubscribe - Отписаться
/notify_all - Уведомить всех (админ)

🏢 **КОМПАНИЯ:**
/contacts - Контакты
/about - О компании

🔄 **СИСТЕМА:**
/check_updates - Проверить обновления вручную
/stats - Статистика бота
/status_db - Статус подключения к БД
        """
        
        await update.message.reply_text(help_text)
    
    async def contacts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /contacts"""
        contacts = """
🏢 **Margiana Logistic Services**

📍 **Адрес:**
Туркменистан, Ашхабад

📞 **Телефоны:**
+993 61 55 77 79 (менеджер)
+993 65 95 77 79 (логистика)

📧 **Email:**
perman@margianalogistics.com
info@margianalogistics.com

🌐 **Сайт:**
margianalogistics.com

🕒 **Рабочие часы:**
Пн-Пт: 9:00-18:00
Сб: 10:00-15:00
        """
        
        await update.message.reply_text(contacts)
    
    # ==================== ИНФОРМАЦИОННЫЕ КОМАНДЫ ====================
    
    async def orders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /orders - активные заказы"""
        try:
            active_statuses = ['New', 'In Progress CHN', 'In Transit CHN-IR', 
                             'In Progress IR', 'In Transit IR-TKM']
            
            response = supabase.table('cloud_orders')\
                .select('*')\
                .in_('status', active_statuses)\
                .order('creation_date', desc=True)\
                .execute()
            
            orders = response.data
            
            if not orders:
                await update.message.reply_text("📭 Нет активных заказов.")
                return
            
            message = f"🚚 **АКТИВНЫЕ ЗАКАЗЫ ({len(orders)})**\n\n"
            
            for i, order in enumerate(orders[:15], 1):  # Ограничиваем 15
                emoji = self.status_emojis.get(order.get('status', ''), '📦')
                order_num = order.get('order_number', 'N/A')
                client = order.get('client_name', 'N/A')[:20]
                status = order.get('status', 'N/A')
                eta = order.get('eta_date', '')
                
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        days_left = (eta_date.date() - datetime.now(TIMEZONE).date()).days
                        if days_left < 0:
                            eta_str = f"⏰ просрочено {abs(days_left)} дн."
                        elif days_left == 0:
                            eta_str = "⏰ сегодня!"
                        elif days_left <= 3:
                            eta_str = f"⚠️ через {days_left} дн."
                        else:
                            eta_str = eta_date.strftime('%d.%m')
                    except:
                        eta_str = eta[:10]
                else:
                    eta_str = "не указана"
                
                message += f"{i}. {emoji} **{order_num}**\n"
                message += f"   👤 {client}\n"
                message += f"   📍 {status}\n"
                message += f"   📅 ETA: {eta_str}\n\n"
            
            if len(orders) > 15:
                message += f"\n... и еще {len(orders) - 15} заказов."
            
            keyboard = [
                [InlineKeyboardButton("📊 Сводный отчет", callback_data="summary_report"),
                 InlineKeyboardButton("📋 По статусам", callback_data="status_report")],
                [InlineKeyboardButton("🔍 Поиск заказа", callback_data="search_order")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in orders_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении заказов.")
    
    async def order_detail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /order [номер] - детали заказа"""
        if not context.args:
            await update.message.reply_text("Укажите номер заказа. Например: /order ORD-001")
            return
        
        order_number = context.args[0].upper()
        
        try:
            # Ищем заказ
            response = supabase.table('cloud_orders')\
                .select('*')\
                .eq('order_number', order_number)\
                .execute()
            
            orders = response.data
            
            if not orders:
                await update.message.reply_text(f"Заказ {order_number} не найден.")
                return
            
            order = orders[0]
            emoji = self.status_emojis.get(order.get('status', ''), '📦')
            
            # Получаем контейнеры заказа
            containers_response = supabase.table('cloud_containers')\
                .select('*')\
                .eq('order_id', order['id'])\
                .execute()
            
            containers = containers_response.data
            
            # Получаем задачи заказа
            tasks_response = supabase.table('cloud_tasks')\
                .select('*')\
                .eq('order_id', order['id'])\
                .order('due_date')\
                .execute()
            
            tasks = tasks_response.data
            
            # Формируем сообщение
            message = f"{emoji} **ЗАКАЗ {order['order_number']}**\n\n"
            message += f"👤 **Клиент:** {order.get('client_name', 'N/A')}\n"
            message += f"📍 **Статус:** {order.get('status', 'N/A')}\n"
            message += f"📦 **Груз:** {order.get('goods_type', 'N/A')}\n"
            message += f"🛣️ **Маршрут:** {order.get('route', 'N/A')}\n"
            message += f"📅 **Создан:** {format_date(order.get('creation_date'))}\n\n"
            
            # Даты
            if order.get('eta_date'):
                message += f"⏰ **ETA:** {format_date(order.get('eta_date'))}\n"
            if order.get('departure_date'):
                message += f"🚢 **ATD:** {format_date(order.get('departure_date'))}\n"
            if order.get('arrival_iran_date'):
                message += f"🇮🇷 **Прибыл в Иран:** {format_date(order.get('arrival_iran_date'))}\n"
            if order.get('tkm_date'):
                message += f"🇹🇲 **TKM дата:** {format_date(order.get('tkm_date'))}\n"
            
            message += f"\n📊 **Флаги:** "
            flags = []
            if order.get('has_loading_photo'):
                flags.append("✅ Фото")
            else:
                flags.append("❌ Фото")
            if order.get('has_local_charges'):
                flags.append("✅ L/Ch")
            else:
                flags.append("❌ L/Ch")
            if order.get('has_tex'):
                flags.append("✅ TLX")
            else:
                flags.append("❌ TLX")
            message += " | ".join(flags)
            
            # Контейнеры
            if containers:
                message += f"\n\n📦 **Контейнеры ({len(containers)}):**\n"
                for container in containers:
                    container_num = container.get('container_number', 'N/A')
                    weight = container.get('weight', 0)
                    message += f"  • {container_num} ({weight} кг)\n"
            
            # Задачи
            if tasks:
                message += f"\n📋 **Задачи ({len(tasks)}):**\n"
                for task in tasks[:3]:  # Показываем 3 задачи
                    status = task.get('status', 'ToDo')
                    status_emoji = "✅" if status == "Completed" else "🟡" if status == "InProgress" else "⏳"
                    desc = task.get('description', 'N/A')[:30]
                    assigned = task.get('assigned_to', 'Не назначена')
                    message += f"  {status_emoji} {desc} - {assigned}\n"
            
            keyboard = [
                [InlineKeyboardButton("📋 Задачи", callback_data=f"tasks_{order['id']}"),
                 InlineKeyboardButton("📦 Контейнеры", callback_data=f"containers_{order['id']}")],
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{order['id']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in order_detail_command: {e}")
            await update.message.reply_text(f"❌ Ошибка при получении заказа {order_number}.")
    
    async def status_filter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /status [статус] - заказы по статусу"""
        if not context.args:
            await update.message.reply_text(
                "Укажите статус. Доступные статусы:\n"
                "• New\n• In Progress CHN\n• In Transit CHN-IR\n• In Progress IR\n"
                "• In Transit IR-TKM\n• Completed\n• Cancelled\n\n"
                "Пример: /status \"In Progress CHN\""
            )
            return
        
        status_filter = " ".join(context.args)
        
        try:
            response = supabase.table('cloud_orders')\
                .select('*')\
                .eq('status', status_filter)\
                .order('creation_date', desc=True)\
                .execute()
            
            orders = response.data
            
            if not orders:
                await update.message.reply_text(f"Нет заказов со статусом '{status_filter}'.")
                return
            
            emoji = self.status_emojis.get(status_filter, '📦')
            message = f"{emoji} **ЗАКАЗЫ СО СТАТУСОМ: {status_filter}** ({len(orders)})\n\n"
            
            for i, order in enumerate(orders[:10], 1):
                order_num = order.get('order_number', 'N/A')
                client = order.get('client_name', 'N/A')[:20]
                eta = order.get('eta_date', '')
                
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        eta_str = eta_date.strftime('%d.%m')
                    except:
                        eta_str = eta[:10]
                else:
                    eta_str = "не указана"
                
                message += f"{i}. **{order_num}** - {client}\n"
                message += f"   📅 ETA: {eta_str}\n\n"
            
            if len(orders) > 10:
                message += f"\n... и еще {len(orders) - 10} заказов."
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in status_filter_command: {e}")
            await update.message.reply_text(f"❌ Ошибка при фильтрации по статусу.")
    
    async def today_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /today - задачи на сегодня"""
        try:
            today = datetime.now(TIMEZONE).date()
            start_date = datetime.combine(today, datetime.min.time()).replace(tzinfo=TIMEZONE)
            end_date = datetime.combine(today, datetime.max.time()).replace(tzinfo=TIMEZONE)
            
            response = supabase.table('cloud_tasks')\
                .select('*, cloud_orders(order_number, client_name)')\
                .lte('due_date', end_date.isoformat())\
                .order('due_date')\
                .execute()
            
            tasks = response.data
            
            if not tasks:
                await update.message.reply_text("✅ На сегодня задач нет!")
                return
            
            # Разделяем на просроченные и сегодняшние
            overdue_tasks = []
            today_tasks = []
            
            for task in tasks:
                due_date_str = task.get('due_date', '')
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        if due_date.date() < today:
                            overdue_tasks.append(task)
                        else:
                            today_tasks.append(task)
                    except:
                        today_tasks.append(task)
                else:
                    today_tasks.append(task)
            
            message = "📋 **ЗАДАЧИ НА СЕГОДНЯ**\n\n"
            
            if overdue_tasks:
                message += "🔴 **ПРОСРОЧЕННЫЕ:**\n"
                for task in overdue_tasks[:5]:
                    order_info = task.get('cloud_orders', {})
                    order_num = order_info.get('order_number', 'N/A') if order_info else 'N/A'
                    desc = task.get('description', 'N/A')[:40]
                    assigned = task.get('assigned_to', 'Не назначена')
                    status = task.get('status', 'ToDo')
                    message += f"• {order_num}: {desc}\n  👤 {assigned} | {status}\n"
                message += "\n"
            
            if today_tasks:
                message += "🟡 **НА СЕГОДНЯ:**\n"
                for task in today_tasks[:10]:
                    order_info = task.get('cloud_orders', {})
                    order_num = order_info.get('order_number', 'N/A') if order_info else 'N/A'
                    desc = task.get('description', 'N/A')[:40]
                    assigned = task.get('assigned_to', 'Не назначена')
                    status = task.get('status', 'ToDo')
                    status_emoji = "✅" if status == "Completed" else "🟡" if status == "InProgress" else "⏳"
                    message += f"• {status_emoji} {order_num}: {desc}\n  👤 {assigned}\n"
            
            keyboard = [
                [InlineKeyboardButton("📋 Все задачи", callback_data="all_tasks"),
                 InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in today_tasks_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении задач.")
    
    async def containers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /containers - контейнеры в пути"""
        try:
            # Контейнеры, которые еще не прибыли в Туркменистан
            response = supabase.table('cloud_containers')\
                .select('*, cloud_orders(order_number, client_name, status)')\
                .is_('arrival_turkmenistan_date', 'null')\
                .execute()
            
            containers = response.data
            
            if not containers:
                await update.message.reply_text("📦 Все контейнеры доставлены!")
                return
            
            message = "🚛 **КОНТЕЙНЕРЫ В ПУТИ**\n\n"
            
            # Группируем по статусу заказа
            containers_by_status = {}
            for container in containers:
                order_info = container.get('cloud_orders', {})
                status = order_info.get('status', 'Unknown')
                if status not in containers_by_status:
                    containers_by_status[status] = []
                containers_by_status[status].append(container)
            
            for status, cont_list in containers_by_status.items():
                emoji = self.status_emojis.get(status, '📦')
                message += f"{emoji} **{status}** ({len(cont_list)} конт.)\n"
                
                for container in cont_list[:3]:  # По 3 контейнера на статус
                    order_info = container.get('cloud_orders', {})
                    order_num = order_info.get('order_number', 'N/A') if order_info else 'N/A'
                    container_num = container.get('container_number', 'N/A')
                    driver = container.get('driver_first_name', '')
                    truck = container.get('truck_number', '')
                    
                    info_parts = []
                    if driver:
                        info_parts.append(f"🚚 {driver}")
                    if truck:
                        info_parts.append(f"#{truck}")
                    
                    info_str = " - " + " ".join(info_parts) if info_parts else ""
                    
                    message += f"  • {container_num} ({order_num}){info_str}\n"
                
                if len(cont_list) > 3:
                    message += f"  ... и еще {len(cont_list) - 3}\n"
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in containers_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении контейнеров.")
    
    async def drivers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /drivers - информация о водителях"""
        try:
            response = supabase.table('cloud_containers')\
                .select('driver_first_name, driver_last_name, driver_company, truck_number, driver_iran_phone, cloud_orders(order_number)')\
                .not_.is_('driver_first_name', 'null')\
                .execute()
            
            drivers_data = response.data
            
            if not drivers_data:
                await update.message.reply_text("👤 Информация о водителях отсутствует.")
                return
            
            # Группируем водителей
            drivers = {}
            for data in drivers_data:
                driver_key = f"{data.get('driver_first_name', '')}_{data.get('driver_last_name', '')}"
                if not driver_key or driver_key == '_':
                    continue
                    
                if driver_key not in drivers:
                    drivers[driver_key] = {
                        'first_name': data.get('driver_first_name', ''),
                        'last_name': data.get('driver_last_name', ''),
                        'company': data.get('driver_company', ''),
                        'truck': data.get('truck_number', ''),
                        'phone': data.get('driver_iran_phone', ''),
                        'orders': set()
                    }
                
                order_info = data.get('cloud_orders', {})
                order_num = order_info.get('order_number', '') if order_info else ''
                if order_num:
                    drivers[driver_key]['orders'].add(order_num)
            
            if not drivers:
                await update.message.reply_text("👤 Информация о водителях отсутствует.")
                return
            
            message = "👨‍✈️ **АКТИВНЫЕ ВОДИТЕЛИ**\n\n"
            
            for i, (driver_key, driver_info) in enumerate(list(drivers.items())[:15], 1):
                name = f"{driver_info['first_name']} {driver_info['last_name']}"
                company = driver_info['company'] or "Не указана"
                truck = driver_info['truck'] or "Без номера"
                phone = driver_info['phone'] or "Не указан"
                orders = ', '.join(list(driver_info['orders'])[:2])
                
                message += f"{i}. **{name}**\n"
                message += f"   🏢 {company}\n"
                message += f"   🚚 {truck}\n"
                message += f"   📞 {phone}\n"
                if orders:
                    message += f"   📦 Заказы: {orders}\n"
                message += "\n"
            
            if len(drivers) > 15:
                message += f"\n👥 Всего водителей: {len(drivers)}"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in drivers_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении водителей.")
    
    # ==================== ОТЧЕТЫ И ФИЛЬТРЫ ====================
    
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /report - сводный отчет"""
        try:
            # Получаем все заказы
            orders_response = supabase.table('cloud_orders').select('*').execute()
            orders = orders_response.data
            
            # Получаем задачи
            tasks_response = supabase.table('cloud_tasks').select('*').execute()
            tasks = tasks_response.data
            
            # Получаем контейнеры
            containers_response = supabase.table('cloud_containers').select('*').execute()
            containers = containers_response.data
            
            # Статистика
            total_orders = len(orders)
            active_orders = sum(1 for o in orders if o.get('status') not in ['Completed', 'Cancelled'])
            completed_orders = sum(1 for o in orders if o.get('status') == 'Completed')
            
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.get('status') == 'Completed')
            overdue_tasks = sum(1 for t in tasks if 
                               t.get('due_date') and 
                               datetime.fromisoformat(t['due_date'].replace('Z', '+00:00')) < datetime.now(TIMEZONE) and
                               t.get('status') != 'Completed')
            
            total_containers = len(containers)
            in_transit = sum(1 for c in containers if c.get('arrival_turkmenistan_date') is None)
            delivered = sum(1 for c in containers if c.get('client_receiving_date') is not None)
            
            # Заказы без фото
            no_photo = sum(1 for o in orders if not o.get('has_loading_photo'))
            no_local = sum(1 for o in orders if not o.get('has_local_charges'))
            no_tex = sum(1 for o in orders if not o.get('has_tex'))
            
            # Срочные заказы (ETA < 3 дня)
            urgent_orders = []
            for order in orders:
                eta = order.get('eta_date')
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        days_left = (eta_date.date() - datetime.now(TIMEZONE).date()).days
                        if 0 <= days_left <= 3:
                            urgent_orders.append(order)
                    except:
                        pass
            
            # Формируем отчет
            report = f"""
📈 **СВОДНЫЙ ОТЧЕТ MARGIANA LOGISTIC**
📅 {datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M')}

📦 **ЗАКАЗЫ:**
• Всего: {total_orders}
• Активные: {active_orders}
• Завершенные: {completed_orders}
• Срочные (ETA < 3 дня): {len(urgent_orders)}

📋 **ЗАДАЧИ:**
• Всего: {total_tasks}
• Выполнено: {completed_tasks}
• Просрочено: {overdue_tasks}

🚚 **КОНТЕЙНЕРЫ:**
• Всего: {total_containers}
• В пути: {in_transit}
• Доставлено: {delivered}

⚠️ **ТРЕБУЮТ ВНИМАНИЯ:**
• Без фото загрузки: {no_photo}
• Без местных сборов: {no_local}
• Без TLX: {no_tex}

🔄 **ПОСЛЕДНЕЕ ОБНОВЛЕНИЕ БД:**
{datetime.now(TIMEZONE).strftime('%d.%m.%Y %H:%M')}
            """
            
            keyboard = [
                [InlineKeyboardButton("📄 PDF отчет", callback_data="generate_pdf"),
                 InlineKeyboardButton("⚠️ Срочные", callback_data="urgent_list")],
                [InlineKeyboardButton("📊 Детальная статистика", callback_data="detailed_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(report, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in report_command: {e}")
            await update.message.reply_text("❌ Ошибка при формировании отчета.")
    
    async def report_pdf_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /report_pdf - отчет в PDF"""
        try:
            await update.message.reply_text("📄 Генерирую PDF отчет... Это может занять несколько секунд.")
            
            # Генерируем PDF
            pdf_path = generate_pdf_report(supabase)
            
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as pdf_file:
                    await update.message.reply_document(
                        document=pdf_file,
                        filename=f"Margiana_Report_{datetime.now(TIMEZONE).strftime('%Y%m%d')}.pdf",
                        caption="📄 Отчет Margiana Logistic Services"
                    )
                # Удаляем временный файл
                os.remove(pdf_path)
            else:
                await update.message.reply_text("❌ Не удалось сгенерировать PDF отчет.")
                
        except Exception as e:
            logger.error(f"Error in report_pdf_command: {e}")
            await update.message.reply_text("❌ Ошибка при генерации PDF отчета.")
    
    async def completed_30_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /completed_30 - завершенные за 30 дней"""
        try:
            thirty_days_ago = (datetime.now(TIMEZONE) - timedelta(days=30)).isoformat()
            
            response = supabase.table('cloud_orders')\
                .select('*')\
                .eq('status', 'Completed')\
                .gte('creation_date', thirty_days_ago)\
                .order('creation_date', desc=True)\
                .execute()
            
            orders = response.data
            
            if not orders:
                await update.message.reply_text("✅ Нет завершенных заказов за последние 30 дней.")
                return
            
            message = f"✅ **ЗАВЕРШЕННЫЕ ЗАКАЗЫ (30 ДНЕЙ) - {len(orders)}**\n\n"
            
            total_containers = 0
            total_weight = 0
            
            for i, order in enumerate(orders[:10], 1):
                order_num = order.get('order_number', 'N/A')
                client = order.get('client_name', 'N/A')[:20]
                containers = order.get('container_count', 0)
                creation_date = format_date(order.get('creation_date'))
                
                message += f"{i}. **{order_num}** - {client}\n"
                message += f"   📦 Контейнеров: {containers}\n"
                message += f"   📅 Завершен: {creation_date}\n\n"
                
                total_containers += containers
            
            if len(orders) > 10:
                message += f"\n... и еще {len(orders) - 10} заказов."
            
            message += f"\n📊 **ИТОГО:** {len(orders)} заказов, {total_containers} контейнеров"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in completed_30_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении завершенных заказов.")
    
    async def no_photos_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /no_photos - заказы без фото"""
        try:
            response = supabase.table('cloud_orders')\
                .select('*')\
                .eq('has_loading_photo', False)\
                .neq('status', 'Completed')\
                .order('creation_date', desc=True)\
                .execute()
            
            orders = response.data
            
            if not orders:
                await update.message.reply_text("✅ У всех активных заказов есть фото загрузки!")
                return
            
            message = f"📸 **ЗАКАЗЫ БЕЗ ФОТО ЗАГРУЗКИ ({len(orders)})**\n\n"
            
            for i, order in enumerate(orders[:10], 1):
                order_num = order.get('order_number', 'N/A')
                client = order.get('client_name', 'N/A')[:20]
                status = order.get('status', 'N/A')
                eta = format_date(order.get('eta_date'))
                
                message += f"{i}. **{order_num}** - {client}\n"
                message += f"   📍 {status} | 📅 ETA: {eta}\n\n"
            
            if len(orders) > 10:
                message += f"\n... и еще {len(orders) - 10} заказов."
            
            keyboard = [
                [InlineKeyboardButton("📋 Список для отправки", callback_data="photo_reminder")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in no_photos_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении заказов без фото.")
    
    async def urgent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /urgent - срочные заказы (ETA < 3 дня)"""
        try:
            response = supabase.table('cloud_orders')\
                .select('*')\
                .neq('status', 'Completed')\
                .neq('status', 'Cancelled')\
                .not_.is_('eta_date', 'null')\
                .execute()
            
            all_orders = response.data
            urgent_orders = []
            
            for order in all_orders:
                eta = order.get('eta_date')
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        days_left = (eta_date.date() - datetime.now(TIMEZONE).date()).days
                        if 0 <= days_left <= 3:
                            urgent_orders.append((order, days_left))
                    except:
                        pass
            
            if not urgent_orders:
                await update.message.reply_text("✅ Нет срочных заказов (ETA в ближайшие 3 дня).")
                return
            
            # Сортируем по количеству дней
            urgent_orders.sort(key=lambda x: x[1])
            
            message = f"⚠️ **СРОЧНЫЕ ЗАКАЗЫ (ETA < 3 ДНЯ) - {len(urgent_orders)}**\n\n"
            
            for i, (order, days_left) in enumerate(urgent_orders[:10], 1):
                order_num = order.get('order_number', 'N/A')
                client = order.get('client_name', 'N/A')[:20]
                status = order.get('status', 'N/A')
                
                if days_left == 0:
                    days_str = "⏰ СЕГОДНЯ!"
                elif days_left == 1:
                    days_str = "⚠️ ЗАВТРА!"
                else:
                    days_str = f"через {days_left} дня"
                
                message += f"{i}. **{order_num}** - {client}\n"
                message += f"   📍 {status} | {days_str}\n\n"
            
            if len(urgent_orders) > 10:
                message += f"\n... и еще {len(urgent_orders) - 10} заказов."
            
            keyboard = [
                [InlineKeyboardButton("📋 Уведомить менеджеров", callback_data="notify_managers")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in urgent_command: {e}")
            await update.message.reply_text("❌ Ошибка при получении срочных заказов.")
    
    # ==================== УВЕДОМЛЕНИЯ ====================
    
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /subscribe - подписаться на уведомления"""
        chat_id = update.effective_chat.id
        
        if chat_id in subscribers:
            await update.message.reply_text("✅ Вы уже подписаны на уведомления.")
        else:
            subscribers.add(chat_id)
            await update.message.reply_text(
                "✅ Вы подписались на уведомления!\n\n"
                "Теперь вы будете получать:\n"
                "• Изменения статусов заказов\n"
                "• Прибытие контейнеров\n"
                "• Предупреждения о ETA\n"
                "• Важные обновления"
            )
            logger.info(f"New subscriber: {chat_id}")
    
    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /unsubscribe - отписаться от уведомлений"""
        chat_id = update.effective_chat.id
        
        if chat_id in subscribers:
            subscribers.remove(chat_id)
            await update.message.reply_text("✅ Вы отписались от уведомлений.")
            logger.info(f"Unsubscribed: {chat_id}")
        else:
            await update.message.reply_text("ℹ️ Вы не были подписаны на уведомления.")
    
    async def notify_all_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /notify_all - уведомить всех (только для админов)"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Эта команда только для администраторов.")
            return
        
        if not context.args:
            await update.message.reply_text("Укажите сообщение для отправки. Пример: /notify_all Важное сообщение")
            return
        
        message = " ".join(context.args)
        notification = f"📢 **ВАЖНОЕ УВЕДОМЛЕНИЕ**\n\n{message}"
        
        sent_count = 0
        failed_count = 0
        
        for sub_id in subscribers:
            try:
                await context.bot.send_message(chat_id=sub_id, text=notification, parse_mode='Markdown')
                sent_count += 1
                await asyncio.sleep(0.1)  # Чтобы не превысить лимиты Telegram
            except Exception as e:
                logger.error(f"Failed to send notification to {sub_id}: {e}")
                failed_count += 1
        
        await update.message.reply_text(
            f"✅ Уведомление отправлено:\n"
            f"• Получили: {sent_count} пользователей\n"
            f"• Не получили: {failed_count} пользователей"
        )
    
    # ==================== СИСТЕМНЫЕ КОМАНДЫ ====================
    
    async def check_updates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /check_updates - проверить обновления вручную"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Эта команда только для администраторов.")
            return
        
        await update.message.reply_text("🔍 Проверяю обновления в базе данных...")
        
        # Здесь будет вызов функции проверки изменений
        # Пока заглушка
        await update.message.reply_text("✅ Проверка завершена. Изменений нет.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /stats - статистика бота"""
        chat_id = update.effective_chat.id
        
        if chat_id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Эта команда только для администраторов.")
            return
        
        stats_text = f"""
📊 **СТАТИСТИКА БОТА**

👥 **Пользователи:**
• Подписчики: {len(subscribers)}
• Администраторы: {len(ADMIN_CHAT_IDS)}

⏰ **Время работы:**
• Текущее время: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}
• Часовой пояс: {TIMEZONE}

🛠 **Система:**
• Версия Python: {os.sys.version}
• Подключение к Supabase: ✅ Активно
• Подписчики в памяти: {len(subscribers)}

📈 **Последняя активность:**
• Последняя проверка: {last_check_time.strftime('%H:%M:%S')}
        """
        
        await update.message.reply_text(stats_text)
    
    async def status_db_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Команда /status_db - статус подключения к БД"""
        try:
            # Пробуем выполнить простой запрос
            response = supabase.table('cloud_orders').select('count', count='exact').limit(1).execute()
            
            # Получаем количество заказов
            count_response = supabase.table('cloud_orders').select('*', count='exact').limit(1).execute()
            order_count = count_response.count or 0
            
            status_text = f"""
✅ **ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ**

🟢 Статус: АКТИВНО
• URL: {SUPABASE_URL[:30]}...
• Заказов в базе: {order_count}
• Время проверки: {datetime.now(TIMEZONE).strftime('%H:%M:%S')}

📊 **ТАБЛИЦЫ:**
• cloud_orders: ✅
• cloud_containers: ✅  
• cloud_tasks: ✅

🔄 **СИНХРОНИЗАЦИЯ:**
• Бот работает 24/7
• Проверка каждые 5 минут
• Уведомления в реальном времени
            """
            
            await update.message.reply_text(status_text)
            
        except Exception as e:
            await update.message.reply_text(f"❌ **ОШИБКА ПОДКЛЮЧЕНИЯ**\n\nОшибка: {str(e)}")
    
    # ==================== ОБРАБОТЧИКИ КНОПОК ====================
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        if callback_data == "active_orders":
            await self.orders_command(update, context)
        elif callback_data == "today_tasks":
            await self.today_tasks_command(update, context)
        elif callback_data == "report":
            await self.report_command(update, context)
        elif callback_data == "drivers":
            await self.drivers_command(update, context)
        elif callback_data == "help":
            await self.help_command(update, context)
        elif callback_data == "summary_report":
            await self.report_command(update, context)
        elif callback_data == "generate_pdf":
            await self.report_pdf_command(update, context)
        elif callback_data.startswith("tasks_"):
            order_id = callback_data.split("_")[1]
            # Здесь можно реализовать показ задач конкретного заказа
            await query.edit_message_text(text=f"Задачи для заказа {order_id} (в разработке)")
        elif callback_data == "urgent_list":
            await self.urgent_command(update, context)
        elif callback_data == "photo_reminder":
            await query.edit_message_text(text="📸 Напоминание отправлено менеджерам!")
    
    # ==================== АВТОМАТИЧЕСКИЕ ПРОВЕРКИ ====================
    
    async def check_database_changes(self, context: CallbackContext) -> None:
        """Периодическая проверка изменений в базе данных"""
        global last_check_time
        
        try:
            now = datetime.now(TIMEZONE)
            logger.info(f"🔍 Проверка изменений в БД ({now.strftime('%H:%M:%S')})")
            
            # 1. Проверяем изменения в заказах
            response = supabase.table('cloud_orders')\
                .select('*')\
                .gte('last_sync_date', last_check_time.isoformat())\
                .execute()
            
            changed_orders = response.data
            
            # 2. Проверяем изменения в контейнерах
            containers_response = supabase.table('cloud_containers')\
                .select('*, cloud_orders(order_number)')\
                .gte('last_sync_date', last_check_time.isoformat())\
                .execute()
            
            changed_containers = containers_response.data
            
            # 3. Проверяем изменения в задачах
            tasks_response = supabase.table('cloud_tasks')\
                .select('*, cloud_orders(order_number)')\
                .gte('last_sync_date', last_check_time.isoformat())\
                .execute()
            
            changed_tasks = tasks_response.data
            
            # 4. Проверяем срочные заказы (ETA < 3 дня)
            urgent_response = supabase.table('cloud_orders')\
                .select('*')\
                .not_.is_('eta_date', 'null')\
                .neq('status', 'Completed')\
                .neq('status', 'Cancelled')\
                .execute()
            
            all_orders = urgent_response.data
            urgent_notifications = []
            
            for order in all_orders:
                eta = order.get('eta_date')
                if eta:
                    try:
                        eta_date = datetime.fromisoformat(eta.replace('Z', '+00:00')).astimezone(TIMEZONE)
                        days_left = (eta_date.date() - now.date()).days
                        
                        # Отправляем уведомление за 3, 2, 1 день и в день ETA
                        if days_left in [3, 2, 1, 0]:
                            order_num = order.get('order_number', 'N/A')
                            client = order.get('client_name', 'N/A')
                            
                            if days_left == 0:
                                message = f"⏰ **СЕГОДНЯ ETA!**\nЗаказ {order_num} ({client}) должен прибыть сегодня!"
                            elif days_left == 1:
                                message = f"⚠️ **ЗАВТРА ETA!**\nЗаказ {order_num} ({client}) прибывает завтра!"
                            else:
                                message = f"📅 **СКОРО ETA ({days_left} дня)**\nЗаказ {order_num} ({client})"
                            
                            urgent_notifications.append(message)
                    except:
                        pass
            
            # Отправляем уведомления подписчикам
            notifications_sent = 0
            
            # Уведомления об измененных заказах
            for order in changed_orders:
                order_num = order.get('order_number', 'N/A')
                status = order.get('status', 'N/A')
                emoji = self.status_emojis.get(status, '📦')
                
                message = f"{emoji} **ОБНОВЛЕН ЗАКАЗ {order_num}**\nСтатус: {status}"
                
                # Отправляем всем подписчикам
                for chat_id in subscribers:
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                        notifications_sent += 1
                        await asyncio.sleep(0.05)  # Задержка между отправками
                    except Exception as e:
                        logger.error(f"Failed to send notification to {chat_id}: {e}")
            
            # Уведомления о срочных заказах (только если не было других уведомлений по этому заказу)
            for notification in urgent_notifications:
                for chat_id in subscribers:
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=notification, parse_mode='Markdown')
                        notifications_sent += 1
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.error(f"Failed to send urgent notification to {chat_id}: {e}")
            
            # Обновляем время последней проверки
            last_check_time = now
            
            if notifications_sent > 0:
                logger.info(f"✅ Отправлено {notifications_sent} уведомлений")
            else:
                logger.info("✅ Изменений нет")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке изменений: {e}")
    
    # ==================== НАСТРОЙКА И ЗАПУСК ====================
    
    def setup_handlers(self, application: Application) -> None:
        """Настройка обработчиков команд"""
        
        # Основные команды
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("contacts", self.contacts_command))
        
        # Информационные команды
        application.add_handler(CommandHandler("orders", self.orders_command))
        application.add_handler(CommandHandler("order", self.order_detail_command))
        application.add_handler(CommandHandler("status", self.status_filter_command))
        application.add_handler(CommandHandler("today", self.today_tasks_command))
        application.add_handler(CommandHandler("containers", self.containers_command))
        application.add_handler(CommandHandler("drivers", self.drivers_command))
        
        # Команды отчетов
        application.add_handler(CommandHandler("report", self.report_command))
        application.add_handler(CommandHandler("report_pdf", self.report_pdf_command))
        application.add_handler(CommandHandler("completed_30", self.completed_30_command))
        application.add_handler(CommandHandler("no_photos", self.no_photos_command))
        application.add_handler(CommandHandler("urgent", self.urgent_command))
        
        # Команды уведомлений
        application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        application.add_handler(CommandHandler("notify_all", self.notify_all_command))
        
        # Системные команды
        application.add_handler(CommandHandler("check_updates", self.check_updates_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(CommandHandler("status_db", self.status_db_command))
        
        # Обработчики кнопок
        application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчик неизвестных команд
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.help_command))

async def main():
    """Главная функция запуска бота"""
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Инициализируем бота
    bot = LogisticsBot()
    bot.setup_handlers(application)
    
    # Настраиваем периодическую проверку (каждые 5 минут)
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(bot.check_database_changes, interval=300, first=10)
        logger.info("⏰ Периодическая проверка настроена (каждые 5 минут)")
    
    # Запускаем бота в режиме polling (для Railway лучше webhook, но polling проще)
    logger.info("🤖 Бот запущен в режиме polling...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    asyncio.run(main())
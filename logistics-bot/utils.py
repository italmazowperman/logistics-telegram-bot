"""
Вспомогательные функции
"""

from datetime import datetime
import pytz

TIMEZONE = pytz.timezone('Asia/Ashgabat')

def format_date(date_str: str) -> str:
    """Форматирование даты для отображения"""
    if not date_str:
        return "не указана"
    
    try:
        if 'Z' in date_str:
            date_str = date_str.replace('Z', '+00:00')
        
        dt = datetime.fromisoformat(date_str).astimezone(TIMEZONE)
        return dt.strftime('%d.%m.%Y')
    except:
        return date_str[:10] if date_str else "не указана"

def format_datetime(date_str: str) -> str:
    """Форматирование даты и времени"""
    if not date_str:
        return "не указана"
    
    try:
        if 'Z' in date_str:
            date_str = date_str.replace('Z', '+00:00')
        
        dt = datetime.fromisoformat(date_str).astimezone(TIMEZONE)
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        return date_str[:16] if date_str else "не указана"

def calculate_days_until(date_str: str) -> int:
    """Вычисление дней до даты"""
    if not date_str:
        return None
    
    try:
        if 'Z' in date_str:
            date_str = date_str.replace('Z', '+00:00')
        
        target_date = datetime.fromisoformat(date_str).astimezone(TIMEZONE).date()
        today = datetime.now(TIMEZONE).date()
        
        return (target_date - today).days
    except:
        return None

def status_to_emoji(status: str) -> str:
    """Преобразование статуса в эмодзи"""
    emojis = {
        'New': '🆕',
        'In Progress CHN': '🇨🇳',
        'In Transit CHN-IR': '🚢',
        'In Progress IR': '🇮🇷',
        'In Transit IR-TKM': '🚛',
        'Completed': '✅',
        'Cancelled': '❌'
    }
    return emojis.get(status, '📦')
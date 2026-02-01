import pytz
from datetime import datetime

TIMEZONE = pytz.timezone('Asia/Ashgabat')

def format_date(date_str: str) -> str:
    """Форматирует дату в удобный для чтения вид"""
    if not date_str:
        return "не указана"
    
    try:
        # Убираем Z и добавляем часовой пояс UTC для преобразования
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        
        # Парсим дату
        dt = datetime.fromisoformat(date_str)
        
        # Конвертируем в локальный часовой пояс
        dt_local = dt.astimezone(TIMEZONE)
        
        # Форматируем
        return dt_local.strftime('%d.%m.%Y %H:%M')
    except Exception as e:
        # Возвращаем первые 10 символов (дату без времени)
        return date_str[:10] if date_str else "не указана"


def calculate_days_until(date_str: str) -> int:
    """Рассчитывает сколько дней осталось до указанной даты"""
    if not date_str:
        return None
    
    try:
        # Убираем Z и добавляем часовой пояс UTC для преобразования
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        
        # Парсим дату
        target_date = datetime.fromisoformat(date_str).astimezone(TIMEZONE).date()
        today = datetime.now(TIMEZONE).date()
        
        # Разница в днях
        delta = target_date - today
        return delta.days
    except Exception:
        return None

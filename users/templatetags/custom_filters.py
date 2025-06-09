from django import template
from datetime import timedelta

register = template.Library()

@register.filter
def format_time(value):
    if value is None:
        return "0 секунд"
    
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
    else:
        total_seconds = int(value * 3600)
    
    if total_seconds < 0:
        return "0 секунд"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    time_parts = []

    if hours > 0:
        time_parts.append(f"{hours} ч")
    if minutes > 0 or hours > 0:
        time_parts.append(f"{minutes} м")
    if seconds > 0 or (hours == 0 and minutes == 0):
        time_parts.append(f"{seconds} с")

    return " ".join(time_parts)


@register.filter
def dict_get(dictionary, key):
    """Возвращает значение из словаря по указанному ключу."""
    return dictionary.get(key)


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
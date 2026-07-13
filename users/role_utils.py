"""Общие проверки ролей и фильтры периода для views."""

import datetime as dt

from django.utils import timezone
from django.utils.dateparse import parse_date

DIRECTOR_EMAIL = "albygroup@bk.ru"

MANAGER_ROLES = frozenset({"junior_manager", "manager", "senior_manager"})
SENIOR_MANAGER_ROLES = frozenset({"manager", "senior_manager"})


def is_director(user) -> bool:
    return bool(user.is_authenticated and getattr(user, "email", None) == DIRECTOR_EMAIL)


def is_manager(user) -> bool:
    return bool(user.is_authenticated and getattr(user, "post_user", None) in MANAGER_ROLES)


def can_manage_staff(user) -> bool:
    """Менеджер/старший менеджер — доступ к сотрудникам и сбросу пароля."""
    return bool(user.is_authenticated and getattr(user, "post_user", None) in SENIOR_MANAGER_ROLES)


def get_shift_period(request):
  """
  Возвращает (start_dt, end_dt, filter_mode, date_from_str, date_to_str, selected_month).
  filter_mode: 'range' | 'month'
  """
  date_from_str = (request.GET.get("date_from") or "").strip()
  date_to_str = (request.GET.get("date_to") or "").strip()
  date_from = parse_date(date_from_str) if date_from_str else None
  date_to = parse_date(date_to_str) if date_to_str else None
  now = timezone.now()

  if date_from and date_to:
    start_dt = timezone.make_aware(dt.datetime.combine(date_from, dt.time.min))
    end_dt = timezone.make_aware(
      dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min)
    )
    return start_dt, end_dt, "range", date_from_str, date_to_str, None

  selected_month_str = request.GET.get("month")
  if selected_month_str:
    try:
      selected_month_naive = dt.datetime.strptime(selected_month_str + "-01", "%Y-%m-%d")
      selected_month = timezone.make_aware(selected_month_naive)
    except (ValueError, TypeError):
      selected_month = now
  else:
    selected_month = now

  start_dt = selected_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
  if selected_month.month == 12:
    end_dt = selected_month.replace(
      year=selected_month.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
  else:
    end_dt = selected_month.replace(
      month=selected_month.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
  return start_dt, end_dt, "month", "", "", selected_month


def reset_user_password(user):
  """Сброс пароля; возвращает временный пароль (plain text)."""
  import secrets
  import string

  alphabet = string.ascii_letters + string.digits
  temp_password = "".join(secrets.choice(alphabet) for _ in range(12))
  user.set_password(temp_password)
  user.save(update_fields=["password"])
  return temp_password

"""Общие проверки ролей и фильтры периода для views."""

import datetime as dt
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
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


def director_required(view):
    """Только директор: аноним → login, остальные роли → home."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_director(request.user):
            messages.error(request, "Недостаточно прав.")
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapped


def _parse_date(value):
    try:
        return parse_date(value) if value else None
    except (ValueError, TypeError):
        return None


def _local_midnight(value):
    return timezone.make_aware(dt.datetime.combine(value, dt.time.min))


def get_month_period(request):
    """Local calendar month, with an exclusive right boundary on every screen."""
    today = timezone.localdate()
    try:
        first = dt.datetime.strptime(request.GET.get("month", ""), "%Y-%m").date()
        following = (first.replace(year=first.year + 1, month=1)
                     if first.month == 12 else first.replace(month=first.month + 1))
    except (ValueError, TypeError, OverflowError):
        first = today.replace(day=1)
        following = (first.replace(year=first.year + 1, month=1)
                     if first.month == 12 else first.replace(month=first.month + 1))
    return _local_midnight(first), _local_midnight(following)


def get_shift_period(request):
    """Return the existing shift-filter context, using local calendar boundaries."""
    date_from = _parse_date((request.GET.get("date_from") or "").strip())
    date_to = _parse_date((request.GET.get("date_to") or "").strip())
    if date_from and date_to and date_from <= date_to and date_to < dt.date.max:
        return (_local_midnight(date_from),
                _local_midnight(date_to + dt.timedelta(days=1)),
                "range", date_from.isoformat(), date_to.isoformat(), None)
    start, end = get_month_period(request)
    return start, end, "month", "", "", start


def get_salary_period(request):
    """Existing director date fields; fill omitted bounds without date/time mixing."""
    today = timezone.localdate()
    start = _parse_date(request.GET.get("start_date")) or today.replace(day=1)
    end = _parse_date(request.GET.get("end_date")) or today
    if start == dt.date.max:
        start = today.replace(day=1)
    if end == dt.date.max:
        end = today
    if start > end:
        start, end = end, start
    return (_local_midnight(start), _local_midnight(end + dt.timedelta(days=1)),
            start.isoformat(), end.isoformat())


def reset_user_password(user):
  """Сброс пароля; возвращает временный пароль (plain text)."""
  import secrets
  import string

  alphabet = string.ascii_letters + string.digits
  temp_password = "".join(secrets.choice(alphabet) for _ in range(12))
  user.set_password(temp_password)
  user.save(update_fields=["password"])
  return temp_password

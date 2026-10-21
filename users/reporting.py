"""Shared salary arithmetic: a whole shift belongs to its local start period."""

from collections import defaultdict

from django.conf import settings
from django.utils import timezone


def completed_in_period(queryset, start, end):
    return queryset.filter(end_time__isnull=False, start_time__gte=start, start_time__lt=end)


def saved_rate(entry, owner):
    return entry.hourly_rate if entry.hourly_rate is not None else owner.stavka()


def salaries_by_owner(queryset, owner_field):
    totals = defaultdict(float)
    for entry in queryset.select_related(owner_field):
        owner = getattr(entry, owner_field)
        seconds = max(0, (entry.end_time - entry.start_time).total_seconds())
        totals[owner.pk] += seconds / 3600 * saved_rate(entry, owner)
    return dict(totals)


def shift_history_context(request, owner, *, manager=False, include_active=True):
    from manager2.models import Task, TimeManger
    from users.models import TimeEntry
    from users.role_utils import get_shift_period

    start, end, mode, date_from, date_to, month = get_shift_period(request)
    base = (TimeManger.objects.filter(manager=owner) if manager
            else TimeEntry.objects.filter(user=owner, timer_type="shift"))
    entries = list(completed_in_period(base, start, end).order_by("-start_time"))
    active = base.filter(end_time__isnull=True).first()
    total_seconds = 0
    total_salary = 0
    for entry in entries:
        seconds = max(0, (entry.end_time - entry.start_time).total_seconds())
        entry.display_duration = int(seconds)
        total_seconds += seconds
        total_salary += seconds / 3600 * saved_rate(entry, owner)

    elapsed = 0
    if active:
        limit_name = "TIME_TRACKER_MANAGER_MAX_SECONDS" if manager else "TIME_TRACKER_SHIFT_MAX_SECONDS"
        elapsed = min(max(0, int((timezone.now() - active.start_time).total_seconds())),
                      getattr(settings, limit_name, 24 * 3600))
        if include_active and start <= active.start_time < end:
            total_seconds += elapsed
            total_salary += elapsed / 3600 * saved_rate(active, owner)

    context = {
        "time_entries": entries,
        "filter_mode": mode,
        "selected_month": month,
        "date_from": date_from,
        "date_to": date_to,
        "start_date": start,
        "end_date": end,
        "total_duration": timezone.timedelta(seconds=total_seconds),
        "total_salary": total_salary,
        "active_shift": active,
        "elapsed_time": elapsed,
        "user_stavka": saved_rate(active, owner) if active else owner.stavka(),
        "active_shift_start_timestamp": int(active.start_time.timestamp()) if active else 0,
        "active_in_period": bool(active and start <= active.start_time < end),
        "active_shift_preview": {
            "start": active.start_time.timestamp() if active else 0,
            "rate": saved_rate(active, owner) if active else owner.stavka(),
            "limit": getattr(settings, "TIME_TRACKER_MANAGER_MAX_SECONDS" if manager
                             else "TIME_TRACKER_SHIFT_MAX_SECONDS", 24 * 3600),
            "included": bool(active and start <= active.start_time < end),
            "base_seconds": sum(max(0, (entry.end_time - entry.start_time).total_seconds()) for entry in entries),
            "base_salary": sum(max(0, (entry.end_time - entry.start_time).total_seconds()) / 3600
                               * saved_rate(entry, owner) for entry in entries),
        },
    }
    if manager:
        context["manager"] = owner
    else:
        context["employee"] = owner
        context["active_task"] = Task.objects.filter(
            submitted_by=owner, is_rated=False, is_submitted_for_review=False).first()
    return context


def staff_queryset():
    from users.models import CustomUser
    from users.role_utils import DIRECTOR_EMAIL, MANAGER_ROLES
    return CustomUser.objects.exclude(post_user__in=["unapproved", *MANAGER_ROLES]).exclude(email=DIRECTOR_EMAIL)


def employee_statistics(request, owner):
    from django.db.models import Avg
    from manager2.models import Task, TaskReview
    from users.models import TimeEntry
    from users.role_utils import get_month_period

    start, end = get_month_period(request)
    shifts = completed_in_period(TimeEntry.objects.filter(user=owner, timer_type="shift"), start, end)
    reviews = TaskReview.objects.filter(user=owner)
    tasks = Task.objects.filter(submitted_by=owner, completed=True,
                                created_at__gte=start, created_at__lt=end)
    owner.average_ratings = reviews.aggregate(value=Avg("rating"))["value"]
    owner.avg_rating_annotation = owner.average_ratings
    owner.completed_tasks_count = reviews.filter(
        task__completed=True, task__created_at__gte=start, task__created_at__lt=end).count()
    return {
        "user": owner,
        "user_data": owner,
        "total_salary": salaries_by_owner(shifts, "user").get(owner.pk, 0),
        "total_shift_hours": sum(max(0, (entry.end_time - entry.start_time).total_seconds())
                                 for entry in shifts) / 3600,
        "worked_photos": tasks.distinct().count(),
        "selected_month": start,
        "current_year": timezone.localdate().year,
        "current_month": timezone.localdate().month,
        "start_date": start,
        "end_date": end,
    }


def manager_statistics(request, owner, *, director=False):
    from manager2.models import Task, TaskReview, TimeManger
    from users.role_utils import get_month_period

    start, end = get_month_period(request)
    tasks = Task.objects.filter(created_by=owner, completed=True,
                                created_at__gte=start, created_at__lt=end).select_related("photo")
    reviews = TaskReview.objects.filter(manager=owner, reviewed_at__gte=start, reviewed_at__lt=end)
    if director:
        reviews = reviews.filter(task__completed=True)
    shifts = completed_in_period(TimeManger.objects.filter(manager=owner), start, end)
    owner.created_tasks = tasks.count()
    owner.reviewed_tasks = reviews.count()
    task_count = tasks.distinct().count()
    names = sorted({task.photo.image_name for task in tasks if task.photo.image_name})
    return {
        "user": owner,
        "user_data": owner,
        "total_salary": salaries_by_owner(shifts, "manager").get(owner.pk, 0),
        "total_shift_hours": sum(max(0, (entry.end_time - entry.start_time).total_seconds())
                                 for entry in shifts) / 3600,
        "worked_photos": task_count if director else (", ".join(names) if names else "Нет макетов"),
        "worked_photos_manager": task_count,
        "selected_month": start,
        "current_year": timezone.localdate().year,
        "current_month": timezone.localdate().month,
        "start_date": start,
        "end_date": end,
    }


def salary_report_context(request, *, manager=False):
    from django.db.models import Avg, Count, IntegerField, OuterRef, Prefetch, Subquery
    from manager2.models import Task, TaskReview, TimeManger
    from users.models import CustomUser, TimeEntry
    from users.role_utils import MANAGER_ROLES, get_salary_period

    start, end, start_text, end_text = get_salary_period(request)
    sort_by = request.GET.get("sort_by", "id" if manager else "desc")
    selected_post = request.GET.get("post_user")
    if manager:
        users = CustomUser.objects.filter(is_active=True, post_user__in=MANAGER_ROLES)
        counts = Task.objects.filter(created_by=OuterRef("pk"), completed=True,
                                     created_at__gte=start, created_at__lt=end)
        counts = counts.values("created_by").annotate(value=Count("id")).values("value")
        relation, owner_field = "user_muser", "manager"
        entries = TimeManger.objects.all()
    else:
        users = staff_queryset().filter(is_active=True)
        if selected_post and selected_post not in ["unapproved", *MANAGER_ROLES]:
            users = users.filter(post_user=selected_post)
        elif selected_post in ["unapproved", *MANAGER_ROLES]:
            selected_post = None
        counts = TaskReview.objects.filter(user=OuterRef("pk"), task__completed=True,
                                           task__created_at__gte=start, task__created_at__lt=end)
        counts = counts.values("user").annotate(value=Count("task")).values("value")
        users = users.annotate(average_ratings=Avg("reviews_user__rating"))
        relation, owner_field = "submitted_reviews", "user"
        entries = TimeEntry.objects.filter(timer_type="shift")

    users = users.annotate(completed_tasks_count=Subquery(counts, output_field=IntegerField()))
    sort_fields = {"asc": "big_stavka", "desc": "-big_stavka", "task": "completed_tasks_count",
                   "anti_task": "-completed_tasks_count"}
    if not manager:
        sort_fields.update({"wasc": "average_ratings", "wdesc": "-average_ratings"})
    users = users.order_by(sort_fields.get(sort_by, "id"))
    users = users.prefetch_related(Prefetch(
        relation,
        queryset=Task.objects.filter(completed=True, created_at__gte=start,
                                     created_at__lt=end).select_related("photo"),
        to_attr="report_completed_tasks",
    ))
    user_ids = list(users.values_list("pk", flat=True))
    salaries = salaries_by_owner(completed_in_period(
        entries.filter(**{f"{owner_field}_id__in": user_ids}), start, end), owner_field)
    photo_names = {}
    for user in users:
        names = sorted({task.photo.image_name for task in user.report_completed_tasks
                        if task.photo.image_name})
        photo_names[user.pk] = ", ".join(names) if names else "Нет макетов"
    return {
        "users": users,
        "total_salary": sum(salaries.values()),
        "individual_salaries": salaries,
        "post_user_choices": [choice for choice in CustomUser.USER_TYPE_CHOICES
                              if choice[0] not in ["unapproved", *MANAGER_ROLES]],
        "selected_post_user": selected_post,
        "sort_by": sort_by,
        "start_date": start_text,
        "end_date": end_text,
        "user_worked_photos": photo_names,
        "user_published_photos": photo_names,
    }

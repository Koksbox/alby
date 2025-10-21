from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .managers import CustomUserManager
import random
import string


# ======================
# Модель пользователя
# ======================

class CustomUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = [
        ('unapproved', 'Неутвержденный'),
        ('trainee', 'Стажер'),
        ('junior_employee', 'Младший сотрудник'),
        ('employee', 'Сотрудник'),
        ('senior_employee', 'Старший сотрудник'),
        ('specialist', 'Специалист'),
        ('master', 'Мастер'),
        ('expert', 'Эксперт'),
        ('junior_manager', 'Младший менеджер'),
        ('manager', 'Менеджер'),
        ('senior_manager', 'Старший менеджер'),
    ]

    email = models.EmailField(unique=True, verbose_name=_('Email'))
    full_name = models.CharField(max_length=255, default='', verbose_name=_('ФИО'))
    phone_number = models.CharField(max_length=20, default='', verbose_name=_('Номер телефона'))
    post_user = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='unapproved',
        null=True,
        verbose_name=_('Должность')
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        default='static/img/default_avatar.jpg',
        verbose_name=_('Аватар')
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Дата рождения')
    )

    pending_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        null=True,
        verbose_name=_('Ожидающий тип')
    )
    user_type_confirmed = models.BooleanField(
        default=False,
        verbose_name=_('Тип подтвержден')
    )

    is_active = models.BooleanField(default=False, verbose_name=_('Активен'))
    is_staff = models.BooleanField(default=False, verbose_name=_('Персонал'))
    confirmation_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name=_('Код подтверждения')
    )
    confirmation_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Время отправки кода')
    )

    big_stavka = models.FloatField(
        default=0,
        verbose_name=_('Ставка')
    )
    prize = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Премия')
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number', 'date_of_birth']

    class Meta:
        verbose_name = _('Пользователь')
        verbose_name_plural = _('Пользователи')

    def __str__(self):
        return self.full_name

    def get_post_display(self):
        return dict(self.USER_TYPE_CHOICES).get(self.post_user)

    def is_expired(self):
        expiration_time = self.confirmation_sent_at + timedelta(minutes=5)
        return timezone.now() > expiration_time

    def should_be_deleted(self):
        return not self.is_active and self.is_expired()

    @property
    def average_rating(self):
        reviews = self.reviews_user.filter(rating__isnull=False)
        if not reviews.exists():
            return 0.0
        return round(sum(review.rating for review in reviews) / reviews.count(), 1)

    def update_rating(self):
        self.rating = self.average_rating
        self.save()

    def stavka(self):
        return self.big_stavka if self.big_stavka else self.calculate_default_stavka()

    def calculate_default_stavka(self):
        stavka_map = {
            'trainee': 100,
            'junior_employee': 120,
            'employee': 140,
            'senior_employee': 160,
            'specialist': 180,
            'master': 200,
            'expert': 250,
            'junior_manager': 180,
            'manager': 200,
            'senior_manager': 225,
            'unapproved': 0,
        }
        return stavka_map.get(self.post_user, 0)

    def set_stavka(self, new_stavka):
        from django.utils import timezone
        today = timezone.now().date()

        current = self.stavka_history.filter(end_date__isnull=True).first()
        if current:
            current.end_date = today - timedelta(days=1)
            current.save()

        StavkaHistory.objects.create(
            user=self,
            stavka=new_stavka,
            start_date=today
        )

        self.big_stavka = new_stavka
        self.save(update_fields=['big_stavka'])

    def reset_stavka(self):
        from django.utils import timezone
        today = timezone.now().date()

        default_stavka = self.calculate_default_stavka()

        current = self.stavka_history.filter(end_date__isnull=True).first()
        if current:
            current.end_date = today - timedelta(days=1)
            current.save()

        StavkaHistory.objects.create(
            user=self,
            stavka=default_stavka,
            start_date=today
        )

        self.big_stavka = None
        self.save(update_fields=['big_stavka'])


# ======================
# История ставок — ВЫНЕСЕНА НА ВЕРХНИЙ УРОВЕНЬ!
# ======================

class StavkaHistory(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='stavka_history'
    )
    stavka = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # null = активна сейчас

    class Meta:
        ordering = ['-start_date']
        verbose_name = "История ставки"
        verbose_name_plural = "Истории ставок"

    def __str__(self):
        return f"{self.user} — {self.stavka} ₽/ч с {self.start_date}"


# ======================
# Прочие модели
# ======================

class PasswordResetCode(models.Model):
    email = models.EmailField(unique=True, verbose_name=_('Email'))
    code = models.CharField(max_length=6, verbose_name=_('Код'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Создан'))

    class Meta:
        verbose_name = _('Код сброса пароля')
        verbose_name_plural = _('Коды сброса пароля')

    def generate_code(self):
        self.code = ''.join(random.choices(string.digits, k=6))
        self.save()

    def __str__(self):
        return f"Reset code for {self.email}"


class PromotionRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('accepted', 'Принято'),
        ('rejected', 'Отклонено'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name=_('Пользователь')
    )
    requested_post = models.CharField(
        max_length=255,
        verbose_name=_('Запрашиваемая должность')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Статус')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Создан')
    )

    class Meta:
        verbose_name = _('Запрос на повышение')
        verbose_name_plural = _('Запросы на повышение')

    def __str__(self):
        return f"{self.user.full_name} - {self.requested_post} ({self.status})"


# ======================
# TimeEntry — с улучшением
# ======================

# Импорт Task должен быть корректным. Убедитесь, что приложение `manager2` установлено.
# Если нет — замените на относительный импорт или строку.

class TimeEntry(models.Model):
    TIMER_TYPE_CHOICES = [
        ('task', 'Task Timer'),
        ('shift', 'Shift Timer'),
    ]

    timer_type = models.CharField(
        max_length=10,
        choices=TIMER_TYPE_CHOICES,
        default='task',
        verbose_name=_('Тип таймера')
    )
    task = models.ForeignKey(
        'manager2.Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Задача')
    )
    user = models.ForeignKey(
        CustomUser,  # ← Используем напрямую, а не get_user_model()
        on_delete=models.CASCADE,
        verbose_name=_('Пользователь')
    )
    hourly_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Ставка на момент записи')
    )
    start_time = models.DateTimeField(verbose_name=_('Время начала'))
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Время окончания')
    )

    class Meta:
        verbose_name = _('Запись времени')
        verbose_name_plural = _('Записи времени')

    @property
    def duration(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return 0

    @property
    def duration_seconds(self):
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.timedelta(0)

    def save(self, *args, **kwargs):
        # Автоматически сохраняем ставку на момент создания/обновления записи
        if self.hourly_rate is None and self.user_id:
            self.hourly_rate = self.user.stavka()
        super().save(*args, **kwargs)

    def salary(self):
        effective_rate = self.hourly_rate if self.hourly_rate is not None else self.user.stavka()
        return self.duration * effective_rate

    def __str__(self):
        return f"TimeEntry: {self.user.full_name} from {self.start_time} to {self.end_time}"

    # === СТАРЫЕ МЕТОДЫ (оставлены для совместимости, но НЕ используют историю ставок) ===

    @classmethod
    def total_salary_users(cls):
        return sum(entry.salary() for entry in cls.objects.filter(end_time__isnull=False))

    @classmethod
    def total_salary_users_money_user(cls, start_date=None, end_date=None):
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(start_time__gte=start_date, end_time__lte=end_date)
        return sum(entry.salary() for entry in queryset)

    @classmethod
    def total_salary_for_each_user_user(cls, start_date=None, end_date=None):
        from collections import defaultdict
        salaries = defaultdict(float)
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(start_time__gte=start_date, end_time__lte=end_date)
        for entry in queryset:
            salaries[entry.user.id] += entry.salary()
        return dict(salaries)

    # === НОВЫЙ МЕТОД — с учётом hourly_rate, сохранённой в момент записи ===
    # (Это уже решает вашу задачу, если вы сохраняете hourly_rate при создании записи!)

    @classmethod
    def total_salary_for_each_user_with_saved_rate(cls, start_date=None, end_date=None):
        """
        Использует hourly_rate, сохранённую в момент записи.
        Это гарантирует, что зарплата не зависит от текущей ставки.
        """
        from collections import defaultdict
        salaries = defaultdict(float)
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(start_time__gte=start_date, end_time__lte=end_date)
        for entry in queryset:
            rate = entry.hourly_rate if entry.hourly_rate is not None else entry.user.stavka()
            salaries[entry.user.id] += entry.duration * rate
        return dict(salaries)

    @classmethod
    def boss_total_salary_for_each_user(cls, start_date=None, end_date=None, user_id=None):
        from collections import defaultdict
        salaries = defaultdict(float)
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(start_time__gte=start_date, end_time__lte=end_date)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        for entry in queryset:
            salaries[entry.user.id] += entry.salary()
        return dict(salaries)

    @classmethod
    def auto_stop_long_shifts(cls):
        from django.conf import settings
        max_seconds = getattr(settings, 'TIME_TRACKER_SHIFT_MAX_SECONDS', 24 * 3600)
        now = timezone.now()
        entries = cls.objects.filter(timer_type='shift', end_time__isnull=True)
        for entry in entries:
            elapsed = (now - entry.start_time).total_seconds()
            if elapsed > max_seconds:
                entry.end_time = entry.start_time + timezone.timedelta(seconds=max_seconds)
                entry.save()


# ======================
# История премий
# ======================

class PrizeHistory(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='prize_history',
        verbose_name=_('Сотрудник')
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Сумма премии')
    )
    date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата назначения')
    )

    class Meta:
        verbose_name = _('История премий')
        verbose_name_plural = _('История премий')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.full_name} - {self.amount} руб. ({self.date.strftime('%d.%m.%Y')})"
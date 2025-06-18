from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .managers import CustomUserManager
import random
import string
from django.contrib.auth import get_user_model




class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Расширенная модель пользователя с дополнительными полями и функциональностью.
    """
    USER_TYPE_CHOICES = [
        ('improver', 'Практикант'),
        ('trainee', 'Стажер'),
        ('specialist', 'Специалист'),
        ('expert', 'Эксперт'),
        ('manager', 'Менеджер'),
        ('unapproved', 'Неутвержденный'),
    ]

    # Основные поля
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

    # Поля для подтверждения типа пользователя
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

    # Поля для активации и подтверждения
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

    # Поля для финансов
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
        """Возвращает отображаемое название должности."""
        return dict(self.USER_TYPE_CHOICES).get(self.post_user)

    def is_expired(self):
        expiration_time = self.confirmation_sent_at + timedelta(minutes=5)
        return timezone.now() > expiration_time

    def should_be_deleted(self):
        """Проверяет, должен ли быть удален неактивированный аккаунт."""
        return not self.is_active and self.is_expired()

    @property
    def average_rating(self):
        """Вычисляет средний рейтинг пользователя."""
        reviews = self.reviews_user.filter(rating__isnull=False)
        if not reviews.exists():
            return 0.0
        return round(sum(review.rating for review in reviews) / reviews.count(), 1)

    def update_rating(self):
        """Обновляет рейтинг пользователя."""
        self.rating = self.average_rating
        self.save()

    def stavka(self):
        """Возвращает ставку пользователя."""
        return self.big_stavka if self.big_stavka else self.calculate_default_stavka()

    def calculate_default_stavka(self):
        """Вычисляет ставку по умолчанию в зависимости от должности."""
        stavka_map = {
            'improver': 0,
            'trainee': 100,
            'specialist': 140,
            'expert': 180,
            'manager': 180,
        }
        return stavka_map.get(self.post_user, 0)

    def set_stavka(self, new_stavka):
        """Устанавливает новую ставку пользователя."""
        self.big_stavka = new_stavka
        self.save()

    def reset_stavka(self):
        """Сбрасывает ставку пользователя на значение по умолчанию."""
        self.big_stavka = None
        self.save()

    @classmethod
    def get_all_users(cls):
        """Возвращает список всех пользователей с основными полями."""
        return list(cls.objects.all().values(
            'email', 'full_name', 'phone_number', 'post_user', 'avatar'
        ))

class PasswordResetCode(models.Model):
    """Модель для хранения кодов сброса пароля."""
    email = models.EmailField(unique=True, verbose_name=_('Email'))
    code = models.CharField(max_length=6, verbose_name=_('Код'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Создан'))

    class Meta:
        verbose_name = _('Код сброса пароля')
        verbose_name_plural = _('Коды сброса пароля')

    def generate_code(self):
        """Генерирует 6-значный случайный код для сброса пароля."""
        self.code = ''.join(random.choices(string.digits, k=6))
        self.save()

    def __str__(self):
        return f"Reset code for {self.email}"

User = get_user_model()

class PromotionRequest(models.Model):
    """Модель для запросов на повышение."""
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('accepted', 'Принято'),
        ('rejected', 'Отклонено'),
    ]

    user = models.ForeignKey(
        User,
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

from manager2.models import Task
class TimeEntry(models.Model):
    """Модель для учета рабочего времени."""
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
        User,
        on_delete=models.CASCADE,
        verbose_name=_('Пользователь')
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
        """Вычисляет продолжительность в часах."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return 0

    def salary(self):
        """Вычисляет зарплату за период."""
        return self.duration * self.user.stavka()

    def __str__(self):
        return f"TimeEntry: {self.user.full_name} from {self.start_time} to {self.end_time}"

    @classmethod
    def total_salary_users(cls):
        """Вычисляет общую зарплату всех пользователей."""
        return sum(entry.salary() for entry in cls.objects.all())

    @classmethod
    def total_salary_users_money_user(cls, start_date=None, end_date=None):
        """Вычисляет общую зарплату за период."""
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lte=end_date
            )
        return sum(entry.salary() for entry in queryset)

    @classmethod
    def total_salary_for_each_user_user(cls, start_date=None, end_date=None):
        """Вычисляет зарплату для каждого пользователя за период."""
        from collections import defaultdict
        salaries_by_user = defaultdict(float)
        
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lte=end_date
            )

        for entry in queryset:
            salaries_by_user[entry.user.id] += entry.salary()

        return dict(salaries_by_user)


####################################MANAGER AND DIRECTOR##############################################
    @classmethod
    def boss_total_salary_for_each_user(cls, start_date=None, end_date=None, user_id=None):
        """Рассчитывает зарплату для каждого сотрудника за период с возможностью фильтрации по user_id"""
        from collections import defaultdict

        salaries_by_user = defaultdict(float)
        queryset = cls.objects.filter(end_time__isnull=False)  # Только завершенные записи

        if start_date and end_date:
            queryset = queryset.filter(start_time__gte=start_date, end_time__lte=end_date)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        for entry in queryset:
            salaries_by_user[entry.user.id] += entry.salary()

        return dict(salaries_by_user)

class PrizeHistory(models.Model):
    """Модель для истории премий."""
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

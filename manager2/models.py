from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from users.models import CustomUser
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class TaskTemplate(models.Model):
    """Модель для хранения шаблонов задач."""
    title = models.CharField(
        max_length=200,
        verbose_name="Название шаблона"
    )
    description = models.TextField(
        verbose_name="Описание"
    )
    requirements = models.TextField(
        verbose_name="Требования"
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name="Создал"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_('Публичный шаблон')
    )

    class Meta:
        verbose_name = "Шаблон задачи"
        verbose_name_plural = "Шаблоны задач"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Photo(models.Model):
    """Модель для хранения фотографий и связанной информации."""
    image = models.ImageField(
        upload_to='photos/',
        verbose_name=_('Изображение')
    )
    image_name = models.CharField(
        max_length=255,
        blank=True,
        null=False,
        default=None,
        verbose_name=_('Название изображения')
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Описание')
    )
    requirements = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Требования')
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата загрузки')
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Завершено')
    )
    estimated_time = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Предполагаемое время')
    )
    due_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Срок выполнения')
    )
    assigned_manager = models.ForeignKey(
        CustomUser,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='manager_assigned',
        verbose_name=_('Назначенный менеджер')
    )

    class Meta:
        verbose_name = _('Фотография')
        verbose_name_plural = _('Фотографии')
        ordering = ['-uploaded_at']

    @property
    def url(self):
        """Возвращает URL изображения."""
        return self.image.url

    def __str__(self):
        return f'Photo {self.id} uploaded at {self.uploaded_at}'

class PhotoFile(models.Model):
    """Модель для хранения файлов, связанных с фотографиями."""
    file = models.FileField(
        upload_to='photo_files/',
        verbose_name=_('Файл')
    )
    photo = models.ForeignKey(
        Photo,
        related_name='files',
        on_delete=models.CASCADE,
        verbose_name=_('Фотография')
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата загрузки')
    )

    class Meta:
        verbose_name = _('Файл фотографии')
        verbose_name_plural = _('Файлы фотографий')
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.file.name

class Task(models.Model):
    """Модель для управления задачами."""
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('submitted', 'Отправлена на проверку'),
        ('reviewed', 'Проверена'),
        ('completed', 'Завершена'),
    ]

    photo = models.ForeignKey(
        Photo,
        on_delete=models.CASCADE,
        related_name='tasks',
        default=1,
        verbose_name=_('Фотография')
    )
    template = models.ForeignKey(
        TaskTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        verbose_name=_('Шаблон задачи')
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_('Название')
    )
    description = models.TextField(
        verbose_name=_('Описание')
    )
    requirements = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Требования')
    )
    due_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Срок сдачи')
    )
    layout = models.CharField(
        max_length=100,
        default='default_value',
        verbose_name=_('Макет')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    completion_time = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Время завершения')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name=_('Статус')
    )
    completed = models.BooleanField(
        default=False,
        verbose_name=_('Завершено')
    )
    quality_confirmed = models.BooleanField(
        default=True,
        verbose_name=_('Качество подтверждено')
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='user_muser',
        blank=True,
        null=True,
        verbose_name=_('Создано пользователем')
    )
    is_submitted_for_review = models.BooleanField(
        default=False,
        verbose_name=_('Отправлено на проверку')
    )
    assigned_to = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Назначено на')
    )
    contractor = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Подрядчик')
    )
    time_spent = models.FloatField(
        default=0.0,
        verbose_name=_('Затраченное время')
    )
    earnings = models.FloatField(
        default=0.0,
        verbose_name=_('Заработок')
    )
    assigned_user = models.ManyToManyField(
        User,
        blank=True,
        related_name='tasks_assigned',
        verbose_name=_('Назначенные пользователи')
    )
    max_assigned_users = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Максимальное количество пользователей')
    )
    stopping = models.BooleanField(
        default=False,
        verbose_name=_('Остановлено')
    )
    submitted_by = models.ManyToManyField(
        CustomUser,
        related_name='submitted_reviews',
        verbose_name=_('Отправлено пользователями')
    )
    is_rated = models.BooleanField(
        default=False,
        verbose_name=_('Оценено')
    )
    completed_by_users = models.ManyToManyField(
        CustomUser,
        related_name='completed_tasks',
        blank=True,
        verbose_name=_('Завершено пользователями')
    )
    submitted_by_users_for_review = models.ManyToManyField(
        User,
        related_name='tasks_submitted_for_review',
        blank=True,
        verbose_name=_('Отправлено на проверку пользователями')
    )
    last_modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Последнее изменение')
    )

    class Meta:
        verbose_name = _('Задача')
        verbose_name_plural = _('Задачи')
        ordering = ['-created_at']

    def is_full(self):
        """Проверяет, достигнуто ли максимальное количество назначенных пользователей."""
        return self.assigned_user.count() >= self.max_assigned_users

    def is_submitted_for_review_by_user(self, user):
        """Проверяет, отправлена ли задача на проверку конкретным пользователем."""
        return self.submitted_by_users_for_review.filter(id=user.id).exists()

    def calculate_earnings(self):
        """Вычисляет заработок за задачу."""
        if not self.submitted_by.exists():
            self.earnings = 0.0
        else:
            self.earnings = sum(
                self.time_spent * user.stavka()
                for user in self.submitted_by.all()
            )
        self.save()

    def update_status(self, new_status):
        """Обновляет статус задачи."""
        self.status = new_status
        if new_status == 'completed':
            self.completed = True
        self.save()

    def __str__(self):
        return self.title

class Review(models.Model):
    """Модель для хранения обзоров задач."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('Задача')
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата отправки')
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Заметки')
    )

    class Meta:
        verbose_name = _('Обзор')
        verbose_name_plural = _('Обзоры')
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Обзор для {self.task.title} от {self.submitted_by.full_name} ({self.submitted_by.email})'

class TaskReview(models.Model):
    """Модель для хранения оценок задач."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='task_reviews',
        verbose_name=_('Задача')
    )
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='managed_reviews',
        verbose_name=_('Менеджер')
    )
    rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 11)],
        null=True,
        blank=True,
        verbose_name=_('Оценка')
    )
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Комментарии')
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='reviews_user',
        null=True,
        blank=True,
        verbose_name=_('Пользователь')
    )
    reviewed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата оценки')
    )
    is_notification_sent = models.BooleanField(
        default=False,
        verbose_name=_('Уведомление отправлено')
    )

    class Meta:
        verbose_name = _('Оценка задачи')
        verbose_name_plural = _('Оценки задач')
        unique_together = ('task', 'user')
        ordering = ['-reviewed_at']

    def save(self, *args, **kwargs):
        """Переопределяем метод save для автоматического обновления статуса задачи."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.rating is not None:
            # Обновляем статус задачи при создании оценки
            self.task.update_status('reviewed')
            # Отправляем уведомление пользователю
            self.send_notification()

    def send_notification(self):
        """Отправляет уведомление пользователю о новой оценке."""
        if not self.is_notification_sent and self.user:
            # Здесь будет логика отправки уведомления
            # Например, через email или встроенную систему уведомлений
            self.is_notification_sent = True
            self.save()

    def __str__(self):
        return f'Оценка {self.rating} для {self.user.full_name} за задачу "{self.task.title}"'

class TimeManger(models.Model):
    """Модель для учета рабочего времени менеджеров."""
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='timemanger_set',
        verbose_name=_('Менеджер')
    )
    start_time = models.DateTimeField(
        verbose_name=_('Время начала')
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Время окончания')
    )

    class Meta:
        verbose_name = _('Учет времени менеджера')
        verbose_name_plural = _('Учет времени менеджеров')
        ordering = ['-start_time']

    @property
    def duration(self):
        """Вычисляет продолжительность в часах."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600
        return 0

    @property
    def salary(self):
        """Вычисляет зарплату за период."""
        return self.duration * self.manager.stavka()

    def __str__(self):
        return f"TimeManager: {self.manager.get_full_name()} from {self.start_time} to {self.end_time}"

    @classmethod
    def total_salary_users_money(cls, start_date=None, end_date=None):
        """Вычисляет общую зарплату за период."""
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lte=end_date
            )
        return sum(entry.salary for entry in queryset)

    @classmethod
    def total_salary_for_each_user(cls, start_date=None, end_date=None):
        """Вычисляет зарплату для каждого менеджера за период."""
        from collections import defaultdict
        salaries_by_user = defaultdict(float)

        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lte=end_date
            )

        for entry in queryset:
            salaries_by_user[entry.manager.id] += entry.salary

        return dict(salaries_by_user)

    @classmethod
    def total_salary_users_money_manager(cls, start_date=None, end_date=None):
        """Вычисляет общую зарплату менеджеров за период."""
        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lt=end_date
            )
        return sum(entry.salary for entry in queryset)

    @classmethod
    def total_salary_for_each_user_manager(cls, start_date=None, end_date=None):
        """Вычисляет зарплату для каждого менеджера за период."""
        from collections import defaultdict
        salaries_by_user = defaultdict(float)

        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lt=end_date
            )

        for entry in queryset:
            hourly_rate = entry.manager.stavka()
            duration = (entry.end_time - entry.start_time).total_seconds() / 3600
            salary = hourly_rate * duration
            salaries_by_user[entry.manager.id] += salary

        return dict(salaries_by_user)

    @classmethod
    def boss_total_salary_for_each_user(cls, start_date=None, end_date=None, manager_id=None):
        """Вычисляет зарплату для каждого менеджера за период с возможностью фильтрации."""
        from collections import defaultdict
        salaries = defaultdict(float)

        queryset = cls.objects.filter(end_time__isnull=False)
        if start_date and end_date:
            queryset = queryset.filter(
                start_time__gte=start_date,
                end_time__lte=end_date
            )
        if manager_id:
            queryset = queryset.filter(manager_id=manager_id)

        for entry in queryset:
            salaries[entry.manager.id] += entry.salary

        return dict(salaries)
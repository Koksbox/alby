from django import forms
from django.contrib.auth import get_user_model

from .models import Task, Photo, TaskTemplate
from django import forms
from users.models import CustomUser

class TaskTemplateForm(forms.ModelForm):
    class Meta:
        model = TaskTemplate
        fields = ['title', 'description', 'requirements']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class TaskForm(forms.ModelForm):
    template = forms.ModelChoiceField(
        queryset=TaskTemplate.objects.all(),
        required=False,
        empty_label="Выберите шаблон",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    assigned_user = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(post_user='user'),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Task
        fields = [
            'template', 'title', 'description', 'requirements',
            'max_assigned_users', 'due_date', 'assigned_user'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'max_assigned_users': forms.NumberInput(attrs={'class': 'form-control'}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
        labels = {
            'title': 'Заголовок задачи',
            'description': 'Текст задачи',
            'requirements': 'Требования',
            'max_assigned_users': 'Максимальное количество',
            'due_date': 'Срок сдачи',
            'assigned_user': 'Назначить сотрудника',
        }

    def __init__(self, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        CustomUser = get_user_model()
        # Исключаем пользователей с ролями 'manager' и 'unapproved'
        self.fields['assigned_user'].queryset = CustomUser.objects.exclude(
            post_user__in=['manager', 'unapproved'])

    def clean(self):
        cleaned_data = super().clean()
        assigned_users = cleaned_data.get('assigned_user')
        max_assigned_users = cleaned_data.get('max_assigned_users')

        if assigned_users and max_assigned_users:
            if len(assigned_users) > max_assigned_users:
                self.add_error('assigned_user', f'Превышено максимальное количество сотрудников ({max_assigned_users}).')

    def form_valid(self, form):
        form.instance.created_by = self.request.user  # Устанавливаем текущего пользователя
        return super().form_valid(form)




class AvatarUploadForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['avatar']

class ManagerPhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ['image_name', 'description', 'requirements', 'due_date']
        widgets = {
            'image_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название...',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Введите описание для макета...',
                'rows': 3,
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Введите требования для макета...',
                'rows': 3,
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Введите срок сдачи макета...',
            }),
        }
        labels = {
            'image_name': 'Название:',
            'description': 'Описание:',
            'requirements': 'Требования:',
            'due_date': 'Срок сдачи:',
        }

class PhotoForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ['image', 'image_name', 'description', 'requirements', 'due_date', 'assigned_manager']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'image_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'assigned_manager': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_manager'].queryset = CustomUser.objects.filter(post_user='manager').distinct()
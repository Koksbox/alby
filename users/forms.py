from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import password_validation

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, PasswordResetCode  # Импортируйте ваш кастомный пользователь
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User



class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'full_name', 'phone_number', 'date_of_birth', 'password1', 'password2')
        labels = {
            'email': 'Email',
            'full_name': 'Ф.И.О',
            'phone_number': 'Номер телефона',
            'date_of_birth': 'Дата рождения',
            'password1': 'Пароль',
            'password2': 'Подтверждение пароля',
        }
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ф.И.О'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер телефона'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'ДД-ММ-ГГГГ'}),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите пароль',
                'style': 'width: 95%; padding: 10px; border: none; border-bottom: 2px solid white; background-color: rgba(0, 0, 0, 0.0); color: white; outline: none;'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Подтвердите пароль',
                'style': 'width: 95%; padding: 10px; border: none; border-bottom: 2px solid white; background-color: rgba(0, 0, 0, 0.0); color: white; outline: none;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем help_text для полей пароля
        self.fields['password1'].help_text = 'Пароль должен содержать минимум 8 символов, включая буквы и цифры'
        self.fields['password2'].help_text = 'Введите тот же пароль для подтверждения'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот адрес электронной почты уже используется.')
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not phone:
            raise forms.ValidationError('Номер телефона обязателен')
        # Можно добавить дополнительную валидацию формата номера телефона
        return phone

from django import forms


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'full_name', 'phone_number', 'post_user' , 'date_of_birth', 'is_staff', 'is_active')
        labels = {
            'email': 'Электронная почта',
            'full_name': 'Фамилия Имя Отечество',
            'phone_number': 'Номер телефона',
            'post_user': 'Должность',
            'date_of_birth': 'Дата рождения',
        }
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ф.И.О'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер телефона'}),
            'post_user': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность'}),
            'date_of_birth': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date', 'placeholder': 'ДД-ММ-ГГГГ'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError('Этот адрес электронной почты уже используется.')
        return email

class PasswordResetCodeForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput(), required=True)  # Скрытое поле
    code = forms.CharField(max_length=6, required=True)
    new_password = forms.CharField(widget=forms.PasswordInput(), required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=True)


    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        code = cleaned_data.get('code')
        new_pass = cleaned_data.get("new_password")
        confirm_pass = cleaned_data.get("confirm_password")

        # Проверка существования кода сброса
        if email and code:
            try:
                reset_code = PasswordResetCode.objects.get(email=email, code=code)
                # Проверка срока действия кода (1 час)
                if reset_code.created_at < timezone.now() - timedelta(hours=1):
                    raise forms.ValidationError("Срок действия кода истек")
            except PasswordResetCode.DoesNotExist:
                raise forms.ValidationError("Неверный код или email")

        # Проверка совпадения паролей
        if new_pass and confirm_pass and new_pass != confirm_pass:
            raise forms.ValidationError("Пароли не совпадают")

        # Валидация пароля по стандартам Django
        try:
            password_validation.validate_password(new_pass)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)

        return cleaned_data



class AvatarUploadForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['avatar']


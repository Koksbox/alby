from django import forms
from users.models import CustomUser
from django.contrib import admin
from django.contrib.auth import get_user_model
from manager2.models import PhotoFile, Photo, Task, TaskTemplate

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

class UserForm(forms.ModelForm):
    big_stavka = forms.IntegerField(
        required=False,  # Поле необязательное
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите вашу ставку'
        }),
        label='Ставка'
    )

    class Meta:
        model = CustomUser
        fields = ['full_name', 'phone_number', 'date_of_birth', 'post_user', 'big_stavka']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите полное имя'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер телефона'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'style': 'color: white;',
                'placeholder': 'Выберите дату рождения',
                'type': 'date'
            }),
            'post_user': forms.Select(attrs={
                'class': 'form-control',
                'style': 'color: black; background-color: white;'

            }),
            'big_stavka': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите ставку',
                'min': 0,
                'max': 400,
                'list': 'big_stavka_options'
            })
        }
        labels = {
            'full_name': 'ФИО',
            'phone_number': 'Телефон',
            'date_of_birth': 'Дата рождения',
            'post_user': 'Должность',
            'big_stavka': 'Ставка',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем все поля необязательными
        for field in self.fields.values():
            field.required = False
        if self.instance and self.instance.pk:
            self.initial['big_stavka'] = self.instance.big_stavka

    def save(self, commit=True):
        user = super().save(commit=False)
        # Сохраняем только те значения, которые были переданы
        cleaned_data = self.cleaned_data
        for field_name, value in cleaned_data.items():
            if value is not None and value != '':
                setattr(user, field_name, value)
        if commit:
            user.save()
        return user


    def clean_big_stavka(self):
        big_stavka = self.cleaned_data.get('big_stavka')
        post_user = self.cleaned_data.get('post_user')

        if post_user != 'trainee' and big_stavka == 0:
            raise forms.ValidationError("Ставка не может быть нулевой для должностей кроме практиканта.")

        return big_stavka

class UploadFileForm(forms.ModelForm):
    class Meta:
        model = PhotoFile
        fields = ['file']

class PhotoDescriptionForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'description-input',
                'placeholder': 'Добавьте описание для макета...',
                'rows': 3,
            }),
        }
        labels = {
            'description': 'Описание:',
        }

class AddDescriptionForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ['image_name', 'description', 'requirements', 'due_date', 'assigned_manager']
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
            'assigned_manager': forms.Select(attrs={
                'class': 'form-control',
            }),
        }
        labels = {
            'image_name': 'Название:',
            'description': 'Описание:',
            'requirements': 'Требования:',
            'due_date': 'Срок сдачи:',
            'assigned_manager': 'Назначить менеджера',
        }

    def __init__(self, *args, **kwargs):
        super(AddDescriptionForm, self).__init__(*args, **kwargs)
        CustomUser = get_user_model()
        self.fields['assigned_manager'].queryset = CustomUser.objects.filter(post_user='manager').distinct()

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('id', 'uploaded_at', 'description')
    search_fields = ['description']
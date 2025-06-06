from rest_framework import serializers
from .models import CustomUser  # Импортируйте вашу модель CustomUser

class UserPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser  # Замените на имя вашей модели
        fields = ['email', 'post_user']
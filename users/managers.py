from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _  # Исправлено

class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, full_name="", **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)

        phone_number = extra_fields.pop("phone_number", None)
        date_of_birth = extra_fields.pop("date_of_birth", None)

        user = self.model(
            email=email,
            full_name=full_name or "",
            phone_number=phone_number or "",
            date_of_birth=date_of_birth,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, full_name="", **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email=email, password=password, full_name=full_name, **extra_fields)
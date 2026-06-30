from django.db import models
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

from django_field_encryption import EncryptedTextField

class UserManager(BaseUserManager):
    # К этому нужно вернуться и понять как вызывается и какие парам передаются
    def create_superuser(self, spotify_id, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        user = self.model(spotify_id=spotify_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    spotify_id = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    access_token = EncryptedTextField(blank=True)
    refresh_token = EncryptedTextField(blank=True)
    ai_music_bio = models.TextField(
        max_length=600,
        blank=True,
        null=True,
        verbose_name="AI Описание музыкального вкуса",
    )
    ai_music_bio_updated_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Дата последнего AI-Анализа"
    )
    ai_analysis_count = models.PositiveIntegerField(default=0)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    # Посмотри как это работает
    USERNAME_FIELD = "spotify_id"
    # Посмотри как это работает
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "user"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.display_name or self.spotify_id

    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return self.token_expires_at <= timezone.now()

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager

class CustomUserManager(UserManager):
    def get_by_natural_key(self, username):
        if isinstance(username, str):
            username = username.lower().strip()
        return self.get(**{self.model.USERNAME_FIELD: username})

    def create_user(self, username, email=None, password=None, **extra_fields):
        if email:
            email = email.lower().strip()
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        if email:
            email = email.lower().strip()
        return super().create_superuser(username, email, password, **extra_fields)

class User(AbstractUser):
    email = models.EmailField(unique=True, error_messages={
        'unique': 'A user with that email already exists.',
    })
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

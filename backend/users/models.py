from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    email = models.EmailField(unique=True, error_messages={
        'unique': 'A user with that email already exists.',
    })
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ['email', 'full_name']

    def __str__(self):
        return self.username

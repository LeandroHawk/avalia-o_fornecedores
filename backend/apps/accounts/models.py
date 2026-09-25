from django.conf import settings
from django.db import models

from backend.apps.core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    class Role(models.TextChoices):
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
        COMPRAS = "COMPRAS", "Compras"
        FORNECEDOR = "FORNECEDOR", "Fornecedor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FORNECEDOR)
    telefone = models.CharField(max_length=30, blank=True)
    cargo = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

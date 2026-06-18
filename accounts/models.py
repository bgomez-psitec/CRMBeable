from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    EMPLEADO = 'empleado', 'Empleado'
    CEO = 'ceo', 'CEO'


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLEADO)
    mfa_enabled = models.BooleanField('MFA activado', default=False)
    assigned_companies = models.ManyToManyField(
        'crm.Company', blank=True, related_name='assigned_employees',
        help_text='Participadas visibles para un usuario con rol empleado',
    )
    company = models.ForeignKey(
        'crm.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='ceos',
        help_text='Participada del usuario con rol CEO',
    )

    def __str__(self):
        return self.get_full_name() or self.username

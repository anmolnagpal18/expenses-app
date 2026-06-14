import uuid
from datetime import datetime
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

FAR_FUTURE = timezone.make_aware(datetime(9999, 12, 31))

class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    base_currency = models.CharField(max_length=3, default='INR')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Membership(models.Model):
    ROLE_CHOICES = (
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
    joined_at = models.DateTimeField()
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user", "joined_at"],
                name="unique_membership_period_start"
            )
        ]

    @property
    def is_active(self):
        now = timezone.now()
        if self.left_at:
            return self.joined_at <= now <= self.left_at
        return self.joined_at <= now

    @property
    def membership_duration(self):
        end = self.left_at if self.left_at else timezone.now()
        duration = end - self.joined_at
        return max(0, duration.days)

    def clean(self):
        # 1. Validate left_at > joined_at
        if self.left_at and self.left_at <= self.joined_at:
            raise ValidationError("left_at must be strictly after joined_at.")

        # 2. Prevent overlapping membership periods for the same user in the same group
        qs = Membership.objects.filter(group=self.group, user=self.user)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        for other in qs:
            self_end = self.left_at if self.left_at else FAR_FUTURE
            other_end = other.left_at if other.left_at else FAR_FUTURE
            
            if not (self_end < other.joined_at or other_end < self.joined_at):
                raise ValidationError("Membership periods for a user in a group cannot overlap.")

        # 3. Enforce that group must have at least one OWNER
        if not self._state.adding:
            old_instance = Membership.objects.get(pk=self.pk)
            if old_instance.role == 'OWNER' and self.role != 'OWNER':
                other_owners = Membership.objects.filter(group=self.group, role='OWNER').exclude(pk=self.pk)
                if not other_owners.exists():
                    raise ValidationError("A group must have at least one OWNER.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Prevent deleting the only OWNER
        if self.role == 'OWNER':
            other_owners = Membership.objects.filter(group=self.group, role='OWNER').exclude(pk=self.pk)
            if not other_owners.exists():
                raise ValidationError("Cannot delete the only OWNER of the group.")
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} in {self.group.name} ({self.role})"

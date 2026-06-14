import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

class StaticExchangeRate(models.Model):
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['from_currency', 'to_currency'],
                name='unique_currency_pair'
            )
        ]
        ordering = ['from_currency', 'to_currency']

    def __str__(self):
        return f"{self.from_currency} -> {self.to_currency}: {self.rate}"

class Expense(models.Model):
    SOURCE_CHOICES = (
        ("MANUAL", "Manual"),
        ("CSV_IMPORT", "CSV Import"),
        ("SEED", "Seed"),
    )
    SPLIT_CHOICES = (
        ('equal', 'Equal'),
        ('percentage', 'Percentage'),
        ('exact', 'Exact'),
        ('shares', 'Shares'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    description = models.CharField(max_length=255)
    date = models.DateField()
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)
    split_type = models.CharField(max_length=20, choices=SPLIT_CHOICES)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_expenses'
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="MANUAL"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.description} ({self.original_amount} {self.currency})"

class ExpenseContribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['expense', 'user'],
                name='unique_expense_contribution'
            ),
            models.CheckConstraint(
                check=models.Q(amount_paid__gt=0),
                name='contribution_amount_paid_positive'
            )
        ]

    def __str__(self):
        return f"{self.user.email} paid {self.amount_paid} for {self.expense.description}"

class ExpenseSplit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='splits'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='splits'
    )
    share_value = models.DecimalField(max_digits=12, decimal_places=2)
    amount_owed = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['expense', 'user'],
                name='unique_expense_split'
            ),
            models.CheckConstraint(
                check=models.Q(amount_owed__gte=0),
                name='split_amount_owed_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.user.email} owes {self.amount_owed} for {self.expense.description}"

class Settlement(models.Model):
    SOURCE_CHOICES = (
        ("MANUAL", "Manual"),
        ("CSV_IMPORT", "CSV Import"),
        ("SEED", "Seed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='settlements'
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_settlements'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_settlements'
    )
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)
    settlement_date = models.DateField()
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="MANUAL"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~models.Q(from_user=models.F('to_user')),
                name='settlement_users_distinct'
            ),
            models.CheckConstraint(
                check=models.Q(original_amount__gt=0),
                name='settlement_amount_positive'
            )
        ]

    def clean(self):
        super().clean()
        if self.from_user == self.to_user:
            raise ValidationError("from_user and to_user must be distinct users.")
        if self.original_amount and self.original_amount <= 0:
            raise ValidationError("original_amount must be strictly positive.")

        # Validation: check both users belong to the group (active or historical)
        if self.group and self.from_user and self.to_user:
            from groups.repositories import MembershipRepository
            from_memberships = MembershipRepository.get_user_membership_in_group(self.group.id, self.from_user.id)
            to_memberships = MembershipRepository.get_user_membership_in_group(self.group.id, self.to_user.id)
            
            if not from_memberships.exists():
                raise ValidationError(f"Payer ({self.from_user.email}) must be a member of the group (historical or active).")
            if not to_memberships.exists():
                raise ValidationError(f"Payee ({self.to_user.email}) must be a member of the group (historical or active).")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_user.email} -> {self.to_user.email}: {self.original_amount} {self.currency}"

class BalanceSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='balance_snapshots'
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_snapshots'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_snapshots'
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    calculation_version = models.IntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "from_user", "to_user"],
                name="unique_group_user_pair"
            )
        ]
        ordering = ['group', 'from_user', 'to_user']

    def __str__(self):
        return f"{self.group.name}: {self.from_user.email} -> {self.to_user.email} balance: {self.balance}"

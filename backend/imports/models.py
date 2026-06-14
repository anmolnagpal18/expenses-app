import uuid
from django.db import models
from django.conf import settings

class ImportBatch(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('REVIEW_REQUIRED', 'Review Required'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        related_name='import_batches'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_batches'
    )
    original_filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    total_rows = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Import Batch'
        verbose_name_plural = 'Import Batches'

    def __str__(self):
        return f"Batch {self.original_filename} ({self.status})"

class ImportRow(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('FLAGGED', 'Flagged'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name='rows'
    )
    row_number = models.IntegerField()
    raw_data = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    processing_notes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['row_number']
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'row_number'],
                name='unique_batch_row_number'
            )
        ]
        verbose_name = 'Import Row'
        verbose_name_plural = 'Import Rows'

    def __str__(self):
        return f"Row {self.row_number} of Batch {self.batch.original_filename}"

class ImportAnomaly(models.Model):
    ANOMALY_CHOICES = (
        ('DUPLICATE_EXPENSE', 'Duplicate Expense'),
        ('CONFLICTING_DUPLICATE', 'Conflicting Duplicate'),
        ('UNKNOWN_MEMBER', 'Unknown Member'),
        ('MEMBERSHIP_VIOLATION', 'Membership Violation'),
        ('INVALID_SPLIT', 'Invalid Split'),
        ('INVALID_CURRENCY', 'Invalid Currency'),
        ('NEGATIVE_AMOUNT', 'Negative Amount'),
        ('SETTLEMENT_AS_EXPENSE', 'Settlement as Expense'),
        ('MISSING_HEADERS', 'Missing Headers'),
    )

    SEVERITY_CHOICES = (
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name='anomalies'
    )
    row = models.ForeignKey(
        ImportRow,
        on_delete=models.CASCADE,
        related_name='anomalies',
        null=True,
        blank=True
    )
    anomaly_type = models.CharField(
        max_length=50,
        choices=ANOMALY_CHOICES
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES
    )
    description = models.TextField()
    is_resolved = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Import Anomaly'
        verbose_name_plural = 'Import Anomalies'

    def __str__(self):
        row_num = self.row.row_number if self.row else 'Batch'
        return f"{self.anomaly_type} ({self.severity}) on Row {row_num}"


class ImportResolution(models.Model):
    ACTION_CHOICES = (
        ("IGNORE", "Ignore"),
        ("MERGE", "Merge"),
        ("MAP_USER", "Map User"),
        ("CREATE_USER", "Create User"),
        ("CONVERT_TO_SETTLEMENT", "Convert To Settlement"),
        ("KEEP_BOTH", "Keep Both"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    anomaly = models.OneToOneField(
        ImportAnomaly,
        on_delete=models.CASCADE,
        related_name='resolution'
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='resolutions'
    )
    action_taken = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES
    )
    notes = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Import Resolution'
        verbose_name_plural = 'Import Resolutions'

    def __str__(self):
        row_num = self.anomaly.row.row_number if self.anomaly.row else 'Batch'
        return f"Resolution for {self.anomaly.anomaly_type} on Row {row_num}"

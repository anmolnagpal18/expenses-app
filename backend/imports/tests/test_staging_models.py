from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.utils import IntegrityError
from decimal import Decimal
import uuid

from groups.models import Group
from imports.models import ImportBatch, ImportRow, ImportAnomaly, ImportResolution
from imports.repositories import (
    ImportBatchRepository,
    ImportRowRepository,
    ImportAnomalyRepository,
    ImportResolutionRepository
)

User = get_user_model()

class StagingImportModelTests(TestCase):
    def setUp(self):
        # Create users
        self.user_a = User.objects.create_user(
            username='usera', email='usera@gmail.com', full_name='User A', password='Password123'
        )
        self.user_b = User.objects.create_user(
            username='userb', email='userb@gmail.com', full_name='User B', password='Password123'
        )

        # Create group
        self.group = Group.objects.create(
            name='Import Group', base_currency='INR', created_by=self.user_a
        )

        # Create basic batch
        self.batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.user_a,
            original_filename='expenses.csv',
            status='PENDING'
        )

    # --- Model Tests ---

    def test_import_batch_creation_and_defaults(self):
        self.assertEqual(self.batch.status, 'PENDING')
        self.assertIsNotNone(self.batch.uploaded_at)
        self.assertIsNone(self.batch.approved_at)
        self.assertEqual(str(self.batch), f"Batch expenses.csv (PENDING)")

    def test_import_row_creation_and_defaults(self):
        row = ImportRow.objects.create(
            batch=self.batch,
            row_number=1,
            raw_data={"amount": "100.00", "description": "Coffee"},
            status='PENDING'
        )
        self.assertEqual(row.status, 'PENDING')
        self.assertEqual(row.processing_notes, [])
        self.assertEqual(str(row), f"Row 1 of Batch expenses.csv")

    def test_import_row_unique_constraint(self):
        ImportRow.objects.create(
            batch=self.batch,
            row_number=1,
            raw_data={"amount": "100.00"},
            status='PENDING'
        )
        with self.assertRaises(IntegrityError):
            ImportRow.objects.create(
                batch=self.batch,
                row_number=1,
                raw_data={"amount": "200.00"},
                status='PENDING'
            )

    def test_import_anomaly_creation_and_defaults(self):
        row = ImportRow.objects.create(
            batch=self.batch,
            row_number=1,
            raw_data={"amount": "-10.00"},
            status='FLAGGED'
        )
        anomaly = ImportAnomaly.objects.create(
            batch=self.batch,
            row=row,
            anomaly_type='NEGATIVE_AMOUNT',
            severity='ERROR',
            description='Amount cannot be negative',
            is_resolved=False
        )
        self.assertEqual(anomaly.anomaly_type, 'NEGATIVE_AMOUNT')
        self.assertEqual(anomaly.severity, 'ERROR')
        self.assertFalse(anomaly.is_resolved)
        self.assertEqual(str(anomaly), "NEGATIVE_AMOUNT (ERROR) on Row 1")

    def test_import_resolution_creation(self):
        row = ImportRow.objects.create(
            batch=self.batch,
            row_number=1,
            raw_data={"amount": "-10.00"},
            status='FLAGGED'
        )
        anomaly = ImportAnomaly.objects.create(
            batch=self.batch,
            row=row,
            anomaly_type='NEGATIVE_AMOUNT',
            severity='ERROR',
            description='Amount cannot be negative'
        )
        resolution = ImportResolution.objects.create(
            anomaly=anomaly,
            resolved_by=self.user_a,
            action_taken='IGNORE',
            notes='Ignored negative amount since it is offset'
        )
        self.assertEqual(resolution.action_taken, 'IGNORE')
        self.assertEqual(resolution.resolved_by, self.user_a)
        self.assertIsNotNone(resolution.resolved_at)
        self.assertEqual(str(resolution), f"Resolution for NEGATIVE_AMOUNT on Row 1")


class StagingImportRepositoryTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='usera', email='usera@gmail.com', password='Password123'
        )
        self.group = Group.objects.create(
            name='Repository Group', base_currency='INR', created_by=self.user_a
        )

    # --- ImportBatchRepository ---

    def test_batch_repository_crud(self):
        # Create
        batch = ImportBatchRepository.create_batch(
            group=self.group,
            uploaded_by=self.user_a,
            original_filename='test.csv'
        )
        self.assertIsNotNone(batch.id)

        # Get by id
        fetched = ImportBatchRepository.get_by_id(batch.id)
        self.assertEqual(fetched.original_filename, 'test.csv')

        # Get by invalid id
        self.assertIsNone(ImportBatchRepository.get_by_id(uuid.uuid4()))
        self.assertIsNone(ImportBatchRepository.get_by_id('invalid-uuid'))

        # Update Status
        updated = ImportBatchRepository.update_status(batch.id, 'APPROVED')
        self.assertEqual(updated.status, 'APPROVED')

        # Get group batches
        batches = ImportBatchRepository.get_group_batches(self.group.id)
        self.assertEqual(batches.count(), 1)

    # --- ImportRowRepository ---

    def test_row_repository_crud(self):
        batch = ImportBatchRepository.create_batch(self.group, self.user_a, 'test.csv')

        # Create
        row = ImportRowRepository.create_row(
            batch=batch,
            row_number=1,
            raw_data={"test": "data"},
            processing_notes=["Note 1"]
        )
        self.assertIsNotNone(row.id)

        # Get by id
        fetched = ImportRowRepository.get_by_id(row.id)
        self.assertEqual(fetched.row_number, 1)
        self.assertEqual(fetched.processing_notes, ["Note 1"])

        # Get by invalid id
        self.assertIsNone(ImportRowRepository.get_by_id(uuid.uuid4()))
        self.assertIsNone(ImportRowRepository.get_by_id('invalid-uuid'))

        # Update Status
        updated = ImportRowRepository.update_status(row.id, 'APPROVED')
        self.assertEqual(updated.status, 'APPROVED')

        # Bulk Create
        row2 = ImportRow(batch=batch, row_number=2, raw_data={"amount": 20}, status='PENDING')
        row3 = ImportRow(batch=batch, row_number=3, raw_data={"amount": 30}, status='PENDING')
        ImportRowRepository.bulk_create_rows([row2, row3])

        # Get batch rows
        rows = ImportRowRepository.get_batch_rows(batch.id)
        self.assertEqual(rows.count(), 3)

    # --- ImportAnomalyRepository ---

    def test_anomaly_repository_crud(self):
        batch = ImportBatchRepository.create_batch(self.group, self.user_a, 'test.csv')
        row = ImportRowRepository.create_row(batch, 1, {"amount": -10})

        # Create
        anomaly = ImportAnomalyRepository.create_anomaly(
            batch=batch,
            row=row,
            anomaly_type='NEGATIVE_AMOUNT',
            severity='ERROR',
            description='Error details'
        )
        self.assertIsNotNone(anomaly.id)

        # Get by id
        fetched = ImportAnomalyRepository.get_by_id(anomaly.id)
        self.assertEqual(fetched.anomaly_type, 'NEGATIVE_AMOUNT')

        # Get by invalid id
        self.assertIsNone(ImportAnomalyRepository.get_by_id(uuid.uuid4()))
        self.assertIsNone(ImportAnomalyRepository.get_by_id('invalid-uuid'))

        # Bulk Create
        anomaly2 = ImportAnomaly(batch=batch, row=row, anomaly_type='INVALID_CURRENCY', severity='WARNING', description='Warning details')
        ImportAnomalyRepository.bulk_create_anomalies([anomaly2])

        # Get row and batch anomalies
        self.assertEqual(ImportAnomalyRepository.get_row_anomalies(row.id).count(), 2)
        self.assertEqual(ImportAnomalyRepository.get_batch_anomalies(batch.id).count(), 2)

    # --- ImportResolutionRepository ---

    def test_resolution_repository_crud(self):
        batch = ImportBatchRepository.create_batch(self.group, self.user_a, 'test.csv')
        row = ImportRowRepository.create_row(batch, 1, {"amount": -10})
        anomaly = ImportAnomalyRepository.create_anomaly(batch, row, 'NEGATIVE_AMOUNT', 'ERROR', 'Error')

        # Create
        resolution = ImportResolutionRepository.create_resolution(
            anomaly=anomaly,
            resolved_by=self.user_a,
            action_taken='IGNORE',
            notes='Ignored'
        )
        self.assertIsNotNone(resolution.id)

        # Get by id
        fetched = ImportResolutionRepository.get_by_id(resolution.id)
        self.assertEqual(fetched.action_taken, 'IGNORE')

        # Get by invalid id
        self.assertIsNone(ImportResolutionRepository.get_by_id(uuid.uuid4()))
        self.assertIsNone(ImportResolutionRepository.get_by_id('invalid-uuid'))

        # Get by anomaly id
        fetched_by_anomaly = ImportResolutionRepository.get_anomaly_resolution(anomaly.id)
        self.assertEqual(fetched_by_anomaly.id, resolution.id)
        self.assertIsNone(ImportResolutionRepository.get_anomaly_resolution(uuid.uuid4()))

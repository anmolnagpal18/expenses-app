from datetime import date, timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from groups.models import Group, Membership
from expenses.models import Expense, Settlement, StaticExchangeRate
from imports.models import ImportAnomaly, ImportBatch, ImportRow, ImportResolution
from imports.services import ImportResolutionService

User = get_user_model()


def make_user(username, email, full_name="Test User", password="TestPassword123"):
    return User.objects.create_user(
        username=username, email=email, full_name=full_name, password=password
    )


class ResolutionWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.alice = make_user("alice", "alice@test.com", full_name="Alice Smith")
        self.bob = make_user("bob", "bob@test.com", full_name="Bob Jones")
        self.outsider = make_user("outsider", "outsider@test.com", full_name="Outside User")

        # Group
        self.group = Group.objects.create(
            name="Test Group", base_currency="INR", created_by=self.alice
        )

        joined = timezone.now() - timedelta(days=730)
        Membership.objects.create(group=self.group, user=self.alice, role="OWNER", joined_at=joined)
        Membership.objects.create(group=self.group, user=self.bob, role="MEMBER", joined_at=joined)

        # Batch
        self.batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.alice,
            original_filename="test.csv",
            status="PENDING",
            total_rows=0,
        )

    def _make_row(self, raw_data: dict, row_number: int = 1) -> ImportRow:
        row = ImportRow.objects.create(
            batch=self.batch,
            row_number=row_number,
            raw_data=raw_data,
            status="PENDING",
            processing_notes=["CSV parsed successfully"],
        )
        self.batch.total_rows = max(self.batch.total_rows, row_number)
        self.batch.save()
        return row

    def _clean_row_data(self) -> dict:
        return {
            "date": "2026-06-10",
            "description": "Lunch expense",
            "amount": "120.00",
            "currency": "INR",
            "paid_by": "alice@test.com",
            "participants": "alice@test.com, bob@test.com",
            "split_type": "equal",
            "split_values": "",
            "notes": "Good lunch"
        }

    # =========================================================================
    # Service Tests: resolve_row_anomaly
    # =========================================================================

    def test_service_resolve_anomaly_success(self):
        row = self._make_row(self._clean_row_data())
        anomaly = ImportAnomaly.objects.create(
            batch=self.batch,
            row=row,
            anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR",
            description="Unknown user Priya",
            is_resolved=False,
            metadata={"missing_member": "Priya"}
        )
        row.status = "FLAGGED"
        row.save()
        self.batch.status = "REVIEW_REQUIRED"
        self.batch.save()

        # Resolve via service
        resolution = ImportResolutionService.resolve_row_anomaly(
            row_id=row.id,
            anomaly_id=anomaly.id,
            user=self.alice,
            action_taken="MAP_USER",
            notes="Mapped Priya to Bob",
            resolution_details={"user_id": str(self.bob.id)}
        )

        # Reload
        anomaly.refresh_from_db()
        row.refresh_from_db()
        self.batch.refresh_from_db()

        self.assertTrue(anomaly.is_resolved)
        self.assertEqual(resolution.action_taken, "MAP_USER")
        self.assertEqual(row.status, "APPROVED")
        self.assertEqual(self.batch.status, "PENDING")
        self.assertIn("Resolved anomaly UNKNOWN_MEMBER", row.processing_notes[-1])

    def test_service_resolve_multiple_anomalies(self):
        row = self._make_row(self._clean_row_data())
        anomaly1 = ImportAnomaly.objects.create(
            batch=self.batch,
            row=row,
            anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR",
            description="Unknown user Priya",
            is_resolved=False,
            metadata={"missing_member": "Priya"}
        )
        anomaly2 = ImportAnomaly.objects.create(
            batch=self.batch,
            row=row,
            anomaly_type="INVALID_CURRENCY",
            severity="ERROR",
            description="Currency not supported",
            is_resolved=False,
        )
        row.status = "FLAGGED"
        row.save()
        self.batch.status = "REVIEW_REQUIRED"
        self.batch.save()

        # Resolve one first
        ImportResolutionService.resolve_row_anomaly(
            row_id=row.id,
            anomaly_id=anomaly1.id,
            user=self.alice,
            action_taken="MAP_USER",
            resolution_details={"user_id": str(self.bob.id)}
        )
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED") # Still flagged because anomaly2 is unresolved

        # Resolve second
        ImportResolutionService.resolve_row_anomaly(
            row_id=row.id,
            anomaly_id=anomaly2.id,
            user=self.alice,
            action_taken="IGNORE",
        )
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED") # One resolution was IGNORE, so row becomes REJECTED

    def test_service_resolve_direct_row_approval_and_ignore(self):
        # Direct approval/ignore for clean/pending rows
        row1 = self._make_row(self._clean_row_data(), row_number=1)
        row2 = self._make_row(self._clean_row_data(), row_number=2)

        # Approve row1
        ImportResolutionService.resolve_row_anomaly(
            row_id=row1.id,
            anomaly_id=None,
            user=self.alice,
            action_taken="APPROVE"
        )
        row1.refresh_from_db()
        self.assertEqual(row1.status, "APPROVED")

        # Ignore row2
        ImportResolutionService.resolve_row_anomaly(
            row_id=row2.id,
            anomaly_id=None,
            user=self.alice,
            action_taken="IGNORE"
        )
        row2.refresh_from_db()
        self.assertEqual(row2.status, "REJECTED")

    # =========================================================================
    # Service Tests: commit_batch & production creation
    # =========================================================================

    def test_service_commit_batch_success(self):
        # Row 1 is APPROVED, Row 2 is REJECTED, Row 3 is PENDING (unapproved)
        row1 = self._make_row(self._clean_row_data(), row_number=1)
        row2 = self._make_row(self._clean_row_data(), row_number=2)
        row3 = self._make_row(self._clean_row_data(), row_number=3)

        row1.status = "APPROVED"
        row1.save()
        row2.status = "REJECTED"
        row2.save()
        row3.status = "PENDING"
        row3.save()

        # Commit
        batch = ImportResolutionService.commit_batch(self.batch.id, self.alice)

        self.assertEqual(batch.status, "APPROVED")
        self.assertIsNotNone(batch.approved_at)
        
        # Verify only 1 expense was created (for row1, not row2 or row3)
        self.assertEqual(Expense.objects.filter(group=self.group).count(), 1)
        expense = Expense.objects.filter(group=self.group).first()
        self.assertEqual(expense.description, "Lunch expense")
        self.assertEqual(expense.original_amount, Decimal("120.00"))
        self.assertEqual(expense.source, "CSV_IMPORT")

        # Check import summary
        self.assertEqual(batch.import_summary["rows_total"], 3)
        self.assertEqual(batch.import_summary["rows_imported"], 1)
        self.assertEqual(batch.import_summary["rows_rejected"], 2) # Total 3, imported 1, so 2 rejected/skipped
        self.assertEqual(batch.import_summary["anomalies_found"], 0)
        self.assertEqual(batch.import_summary["anomalies_resolved"], 0)

    def test_service_commit_with_map_user_and_create_user(self):
        # Row uses "Priya" (unknown) paid_by, and "Dev" (unknown) participant
        row = self._make_row({
            "date": "2026-06-10",
            "description": "Pizza Party",
            "amount": "90.00",
            "currency": "INR",
            "paid_by": "Priya",
            "participants": "Alice Smith, Dev",
            "split_type": "equal",
            "split_values": "",
        })
        row.status = "APPROVED"
        row.save()

        # Add anomalies
        anomaly_priya = ImportAnomaly.objects.create(
            batch=self.batch, row=row, anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR", description="Unknown Priya", is_resolved=False,
            metadata={"missing_member": "Priya"}
        )
        anomaly_dev = ImportAnomaly.objects.create(
            batch=self.batch, row=row, anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR", description="Unknown Dev", is_resolved=False,
            metadata={"missing_member": "Dev"}
        )

        # Resolve Priya to Bob (MAP_USER)
        ImportResolutionService.resolve_row_anomaly(
            row_id=row.id, anomaly_id=anomaly_priya.id, user=self.alice,
            action_taken="MAP_USER", resolution_details={"user_id": str(self.bob.id)}
        )

        # Resolve Dev to new user (CREATE_USER)
        ImportResolutionService.resolve_row_anomaly(
            row_id=row.id, anomaly_id=anomaly_dev.id, user=self.alice,
            action_taken="CREATE_USER",
            resolution_details={"email": "dev@test.com", "full_name": "Dev Kumar"}
        )

        # Commit batch
        ImportResolutionService.commit_batch(self.batch.id, self.alice)

        # Verify Dev user and Membership created
        dev_user = User.objects.get(email="dev@test.com")
        self.assertEqual(dev_user.full_name, "Dev Kumar")
        self.assertTrue(Membership.objects.filter(group=self.group, user=dev_user).exists())

        # Verify expense payer is Bob, participants are Alice and Dev
        expense = Expense.objects.filter(group=self.group).first()
        self.assertEqual(expense.created_by, self.alice)
        
        # Payers
        contributions = list(expense.contributions.all())
        self.assertEqual(len(contributions), 1)
        self.assertEqual(contributions[0].user, self.bob)
        self.assertEqual(contributions[0].amount_paid, Decimal("90.00"))

        # Splits
        splits = list(expense.splits.all())
        self.assertEqual(len(splits), 2)
        participants = {s.user for s in splits}
        self.assertEqual(participants, {self.alice, dev_user})

    def test_service_commit_convert_to_settlement(self):
        # Row matches settlement pattern
        row = self._make_row({
            "date": "2026-06-10",
            "description": "Settle up transfer",
            "amount": "500.00",
            "currency": "INR",
            "paid_by": "alice@test.com",
            "participants": "bob@test.com",
            "split_type": "equal",
            "split_values": "",
        })
        row.status = "APPROVED"
        row.save()

        anomaly = ImportAnomaly.objects.create(
            batch=self.batch, row=row, anomaly_type="SETTLEMENT_AS_EXPENSE",
            severity="WARNING", description="Settlement pattern detected", is_resolved=False,
        )

        # Resolve by converting
        ImportResolutionService.resolve_row_anomaly(
            row_id=row.id, anomaly_id=anomaly.id, user=self.alice,
            action_taken="CONVERT_TO_SETTLEMENT"
        )

        # Commit
        ImportResolutionService.commit_batch(self.batch.id, self.alice)

        # Verify settlement created, no expense created
        self.assertEqual(Expense.objects.filter(group=self.group).count(), 0)
        self.assertEqual(Settlement.objects.filter(group=self.group).count(), 1)
        
        settlement = Settlement.objects.filter(group=self.group).first()
        self.assertEqual(settlement.from_user, self.alice)
        self.assertEqual(settlement.to_user, self.bob)
        self.assertEqual(settlement.original_amount, Decimal("500.00"))
        self.assertEqual(settlement.source, "CSV_IMPORT")

    def test_service_commit_currency_conversion(self):
        # Create exchange rate from USD to INR
        StaticExchangeRate.objects.create(
            from_currency="USD", to_currency="INR", rate=Decimal("80.00")
        )

        row = self._make_row({
            "date": "2026-06-10",
            "description": "USD Expense",
            "amount": "10.00",
            "currency": "USD",
            "paid_by": "alice@test.com",
            "participants": "bob@test.com",
            "split_type": "equal",
            "split_values": "",
        })
        row.status = "APPROVED"
        row.save()

        # Commit
        ImportResolutionService.commit_batch(self.batch.id, self.alice)

        expense = Expense.objects.filter(group=self.group).first()
        self.assertEqual(expense.currency, "USD")
        self.assertEqual(expense.original_amount, Decimal("10.00"))
        self.assertEqual(expense.converted_amount, Decimal("800.00")) # 10.00 * 80.00

    def test_service_commit_rollback_on_failure(self):
        # Make row 1 valid, but row 2 invalid (e.g. invalid split values count)
        row1 = self._make_row(self._clean_row_data(), row_number=1)
        row2 = self._make_row({
            "date": "2026-06-10",
            "description": "Bad split row",
            "amount": "100.00",
            "currency": "INR",
            "paid_by": "alice@test.com",
            "participants": "alice@test.com, bob@test.com",
            "split_type": "shares",
            "split_values": "5", # Only 1 value, but 2 participants
        }, row_number=2)

        row1.status = "APPROVED"
        row1.save()
        row2.status = "APPROVED"
        row2.save()

        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            ImportResolutionService.commit_batch(self.batch.id, self.alice)

        # Check that NO expense records exist (rollback worked)
        self.assertEqual(Expense.objects.filter(group=self.group).count(), 0)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, "PENDING") # Status not updated to APPROVED

    # =========================================================================
    # API View Tests
    # =========================================================================

    def test_api_batch_detail(self):
        row = self._make_row(self._clean_row_data())
        self.client.force_authenticate(user=self.alice)

        url = f"/api/imports/batches/{self.batch.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.batch.id))
        self.assertEqual(len(response.data["rows"]), 1)
        self.assertEqual(response.data["rows"][0]["id"], str(row.id))

    def test_api_batch_detail_permissions(self):
        url = f"/api/imports/batches/{self.batch.id}/"

        # Unauthenticated
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Forbidden (non-group member)
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_resolve_anomaly(self):
        row = self._make_row(self._clean_row_data())
        anomaly = ImportAnomaly.objects.create(
            batch=self.batch, row=row, anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR", description="Unknown user Priya", is_resolved=False,
            metadata={"missing_member": "Priya"}
        )
        row.status = "FLAGGED"
        row.save()

        self.client.force_authenticate(user=self.alice)
        url = f"/api/imports/rows/{row.id}/resolve/"
        payload = {
            "anomaly_id": str(anomaly.id),
            "action_taken": "MAP_USER",
            "notes": "Mapped via API",
            "resolution_details": {"user_id": str(self.bob.id)}
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        anomaly.refresh_from_db()
        self.assertTrue(anomaly.is_resolved)
        self.assertEqual(anomaly.resolution.notes, "Mapped via API")

    def test_api_commit_batch(self):
        row = self._make_row(self._clean_row_data())
        row.status = "APPROVED"
        row.save()

        self.client.force_authenticate(user=self.alice)
        url = f"/api/imports/batches/{self.batch.id}/commit/"
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["import_summary"]["rows_imported"], 1)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, "APPROVED")

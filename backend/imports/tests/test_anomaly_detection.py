"""
Commit #28 – test(imports): anomaly detection coverage

Covers every detection rule in AnomalyDetectionEngine:
  1. NEGATIVE_AMOUNT
  2. INVALID_CURRENCY
  3. UNKNOWN_MEMBER  (email, username alias, fuzzy name "Aisha K" style)
  4. MEMBERSHIP_VIOLATION
  5. INVALID_SPLIT
  6. SETTLEMENT_AS_EXPENSE
  7. DUPLICATE_EXPENSE  (production, prior batch, intra-batch)
  8. CONFLICTING_DUPLICATE (production, prior batch, intra-batch)

Plus:
  - Multiple anomalies on a single row
  - Clean batch (all rows APPROVED, batch stays PENDING)
  - Mixed batch (some rows APPROVED, some FLAGGED, batch → REVIEW_REQUIRED)
  - Row processing_notes updated with anomaly summaries
  - Return summary dict correctness
  - Detect API endpoint: 200 OK, 401 Unauthenticated, 403 Forbidden, 404 Not Found
  - ImportAnomaly.metadata populated correctly
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from groups.models import Group, Membership
from expenses.models import Expense, StaticExchangeRate
from imports.models import ImportAnomaly, ImportBatch, ImportRow
from imports.anomaly_engine import AnomalyDetectionEngine

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, email, full_name="Test User", password="TestPassword123"):
    return User.objects.create_user(
        username=username, email=email, full_name=full_name, password=password
    )


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class AnomalyDetectionBase(TestCase):
    """
    Creates:
      - alice  (OWNER, joined 2 years ago)
      - bob    (MEMBER, joined 2 years ago)
      - outsider (not in group)
    And a default PENDING ImportBatch.
    """

    def setUp(self):
        self.client = APIClient()

        self.alice = make_user("alice", "alice@test.com", full_name="Alice Smith")
        self.bob   = make_user("bob",   "bob@test.com",   full_name="Bob Jones")
        self.outsider = make_user("outsider", "outsider@test.com", full_name="Outside User")

        self.group = Group.objects.create(
            name="Test Group", base_currency="INR", created_by=self.alice
        )

        joined = timezone.now() - timedelta(days=730)
        Membership.objects.create(group=self.group, user=self.alice, role="OWNER", joined_at=joined)
        Membership.objects.create(group=self.group, user=self.bob,   role="MEMBER", joined_at=joined)

        self.batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.alice,
            original_filename="test.csv",
            status="PENDING",
            total_rows=0,
        )
        self.engine = AnomalyDetectionEngine()

    # ------------------------------------------------------------------ helpers

    def _make_row(self, raw_data: dict, row_number: int = 1) -> ImportRow:
        return ImportRow.objects.create(
            batch=self.batch,
            row_number=row_number,
            raw_data=raw_data,
            status="PENDING",
            processing_notes=["CSV parsed successfully"],
        )

    def _clean_row(self, **overrides) -> dict:
        """Return a valid raw_data dict, optionally overridden."""
        # Use a recent date (10 days ago) that's always within the 730-day membership window
        recent_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        base = {
            "date":         recent_date,
            "description":  "Dinner at restaurant",
            "amount":       "1200.00",
            "currency":     "INR",
            "paid_by":      "alice@test.com",
            "participants": "alice@test.com,bob@test.com",
            "split_type":   "equal",
            "split_values": "",
            "notes":        "",
        }
        base.update(overrides)
        return base

    def _run(self):
        """Shorthand: run detection on self.batch and return result dict."""
        return self.engine.detect_batch_anomalies(self.batch.id)

    def _set_total_rows(self, n: int):
        self.batch.total_rows = n
        self.batch.save()

    def _anomalies_for(self, row, anomaly_type=None):
        qs = ImportAnomaly.objects.filter(row=row)
        if anomaly_type:
            qs = qs.filter(anomaly_type=anomaly_type)
        return qs


# ===========================================================================
# 1. NEGATIVE_AMOUNT
# ===========================================================================

class NegativeAmountTests(AnomalyDetectionBase):

    def test_zero_amount_flagged_with_error_severity(self):
        row = self._make_row(self._clean_row(amount="0"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED")
        a = self._anomalies_for(row, "NEGATIVE_AMOUNT").get()
        self.assertEqual(a.severity, "ERROR")

    def test_negative_amount_flagged(self):
        row = self._make_row(self._clean_row(amount="-500"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED")
        self.assertTrue(self._anomalies_for(row, "NEGATIVE_AMOUNT").exists())

    def test_non_numeric_amount_flagged(self):
        row = self._make_row(self._clean_row(amount="abc"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED")

    def test_positive_amount_no_anomaly(self):
        row = self._make_row(self._clean_row(amount="0.01"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertFalse(self._anomalies_for(row, "NEGATIVE_AMOUNT").exists())

    def test_metadata_contains_raw_value(self):
        row = self._make_row(self._clean_row(amount="-99"))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "NEGATIVE_AMOUNT").get()
        self.assertIn("raw_value", a.metadata)


# ===========================================================================
# 2. INVALID_CURRENCY
# ===========================================================================

class InvalidCurrencyTests(AnomalyDetectionBase):

    def test_group_base_currency_valid(self):
        row = self._make_row(self._clean_row(currency="INR"))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_CURRENCY").exists())

    def test_always_valid_usd_passes(self):
        row = self._make_row(self._clean_row(currency="USD"))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_CURRENCY").exists())

    def test_unknown_currency_flagged_as_warning(self):
        row = self._make_row(self._clean_row(currency="XYZ"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "INVALID_CURRENCY").get()
        self.assertEqual(a.severity, "WARNING")
        self.assertEqual(a.metadata["supplied_currency"], "XYZ")

    def test_empty_currency_flagged_as_error(self):
        row = self._make_row(self._clean_row(currency=""))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "INVALID_CURRENCY").get()
        self.assertEqual(a.severity, "ERROR")

    def test_configured_exchange_rate_currency_accepted(self):
        StaticExchangeRate.objects.create(from_currency="THB", to_currency="INR", rate=Decimal("2.50"))
        row = self._make_row(self._clean_row(currency="THB"))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_CURRENCY").exists())


# ===========================================================================
# 3. UNKNOWN_MEMBER
# ===========================================================================

class UnknownMemberTests(AnomalyDetectionBase):

    def test_unknown_paid_by_flagged(self):
        row = self._make_row(self._clean_row(paid_by="ghost@unknown.com"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "UNKNOWN_MEMBER").get()
        self.assertEqual(a.severity, "ERROR")
        self.assertIn("ghost@unknown.com", a.description)

    def test_unknown_participant_flagged(self):
        row = self._make_row(self._clean_row(participants="alice@test.com,ghost@unknown.com"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(self._anomalies_for(row, "UNKNOWN_MEMBER").exists())

    def test_known_member_by_full_email_passes(self):
        row = self._make_row(self._clean_row(
            paid_by="alice@test.com",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertFalse(self._anomalies_for(row, "UNKNOWN_MEMBER").exists())

    def test_known_member_by_username_passes(self):
        """Username portion (before @) is a valid alias."""
        row = self._make_row(self._clean_row(
            paid_by="alice", participants="alice,bob"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "UNKNOWN_MEMBER").exists())

    def test_known_member_by_first_name_passes(self):
        """Alice Smith → alias 'alice' → should match."""
        row = self._make_row(self._clean_row(
            paid_by="Alice", participants="Alice,Bob"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "UNKNOWN_MEMBER").exists())

    def test_fuzzy_first_name_plus_initial_passes(self):
        """'Alice S' should fuzzy-match 'Alice Smith'."""
        row = self._make_row(self._clean_row(
            paid_by="Alice S", participants="Alice S,Bob J"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "UNKNOWN_MEMBER").exists())

    def test_metadata_contains_possible_matches(self):
        """Unknown name with same first name → possible_matches populated."""
        row = self._make_row(self._clean_row(
            paid_by="Alice Zzz",   # same first name, wrong last
            participants="bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "UNKNOWN_MEMBER").first()
        # Depending on uniqueness, possible_matches may include alice@test.com
        self.assertIn("possible_matches", a.metadata)

    def test_multiple_unknown_members_create_multiple_anomalies(self):
        row = self._make_row(self._clean_row(
            paid_by="ghost1@x.com",
            participants="ghost2@x.com,ghost3@x.com"
        ))
        self._set_total_rows(1)
        self._run()
        unknown_count = self._anomalies_for(row, "UNKNOWN_MEMBER").count()
        self.assertEqual(unknown_count, 3)  # paid_by + 2 participants


# ===========================================================================
# 4. MEMBERSHIP_VIOLATION
# ===========================================================================

class MembershipViolationTests(AnomalyDetectionBase):

    def test_expense_before_member_joined_flagged(self):
        # Alice joined 730 days ago; expense 5 years ago → violation
        old_date = (date.today() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        row = self._make_row(self._clean_row(date=old_date))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        self.assertTrue(self._anomalies_for(row, "MEMBERSHIP_VIOLATION").exists())

    def test_expense_after_member_left_flagged(self):
        membership = Membership.objects.get(group=self.group, user=self.bob)
        membership.left_at = timezone.now() - timedelta(days=365)
        membership.save()

        today = date.today().strftime("%Y-%m-%d")
        row = self._make_row(self._clean_row(
            date=today,
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "MEMBERSHIP_VIOLATION").get()
        self.assertIn("bob@test.com", a.description)
        self.assertIn("expense_date", a.metadata)

    def test_valid_date_during_membership_passes(self):
        recent = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        row = self._make_row(self._clean_row(date=recent))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertFalse(self._anomalies_for(row, "MEMBERSHIP_VIOLATION").exists())


# ===========================================================================
# 5. INVALID_SPLIT
# ===========================================================================

class InvalidSplitTests(AnomalyDetectionBase):

    def test_unknown_split_type_flagged(self):
        row = self._make_row(self._clean_row(split_type="magic", split_values=""))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED")
        a = self._anomalies_for(row, "INVALID_SPLIT").get()
        self.assertEqual(a.severity, "ERROR")
        self.assertIn("supplied_split_type", a.metadata)

    def test_percentage_not_100_flagged(self):
        row = self._make_row(self._clean_row(
            split_type="percentage",
            split_values="40,40",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "INVALID_SPLIT").get()
        self.assertEqual(a.severity, "ERROR")
        self.assertEqual(a.metadata["expected_percentage"], 100)
        self.assertAlmostEqual(a.metadata["actual_percentage"], 80.0)

    def test_percentage_100_passes(self):
        row = self._make_row(self._clean_row(
            split_type="percentage",
            split_values="50,50",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_SPLIT").exists())

    def test_exact_split_mismatch_flagged(self):
        row = self._make_row(self._clean_row(
            amount="1000",
            split_type="exact",
            split_values="400,400",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "INVALID_SPLIT").get()
        self.assertEqual(a.severity, "ERROR")
        self.assertEqual(a.metadata["expected_sum"], "1000")

    def test_exact_split_matches_passes(self):
        row = self._make_row(self._clean_row(
            amount="1000",
            split_type="exact",
            split_values="500,500",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_SPLIT").exists())

    def test_shares_no_values_flagged(self):
        row = self._make_row(self._clean_row(
            split_type="shares", split_values="",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "REJECTED")

    def test_equal_split_no_values_needed(self):
        row = self._make_row(self._clean_row(split_type="equal", split_values=""))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "INVALID_SPLIT").exists())

    def test_count_mismatch_flagged(self):
        row = self._make_row(self._clean_row(
            split_type="shares",
            split_values="1,2,3",
            participants="alice@test.com,bob@test.com"
        ))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "INVALID_SPLIT").get()
        self.assertEqual(a.metadata["split_count"], 3)
        self.assertEqual(a.metadata["participant_count"], 2)


# ===========================================================================
# 6. SETTLEMENT_AS_EXPENSE
# ===========================================================================

class SettlementPatternTests(AnomalyDetectionBase):

    def test_settlement_keywords_flagged(self):
        keywords = ["settlement", "settle", "repay", "reimburse", "paid back", "reimbursement"]
        for kw in keywords:
            with self.subTest(keyword=kw):
                ImportAnomaly.objects.filter(batch=self.batch).delete()
                ImportRow.objects.filter(batch=self.batch).delete()
                self.batch.status = "PENDING"
                self.batch.save()

                row = self._make_row(self._clean_row(description=f"Monthly {kw}"))
                self._set_total_rows(1)
                AnomalyDetectionEngine().detect_batch_anomalies(self.batch.id)

                row.refresh_from_db()
                self.assertEqual(row.status, "FLAGGED", msg=f"Keyword '{kw}' not caught")
                self.assertTrue(
                    ImportAnomaly.objects.filter(row=row, anomaly_type="SETTLEMENT_AS_EXPENSE").exists()
                )

    def test_normal_description_passes(self):
        row = self._make_row(self._clean_row(description="Dinner at restaurant"))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(self._anomalies_for(row, "SETTLEMENT_AS_EXPENSE").exists())

    def test_metadata_contains_description(self):
        row = self._make_row(self._clean_row(description="Bob's settlement"))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "SETTLEMENT_AS_EXPENSE").get()
        self.assertIn("description", a.metadata)


# ===========================================================================
# 7 & 8. DUPLICATE / CONFLICTING DUPLICATE
# ===========================================================================

class DuplicateDetectionTests(AnomalyDetectionBase):

    def _make_production_expense(self, description="Dinner", amount="1200", exp_date=None):
        if exp_date is None:
            # 400 days ago – well within the 730-day membership window
            exp_date = date.today() - timedelta(days=400)
        return Expense.objects.create(
            group=self.group,
            description=description,
            date=exp_date,
            original_amount=Decimal(amount),
            converted_amount=Decimal(amount),
            currency="INR",
            exchange_rate=Decimal("1.0000"),
            split_type="equal",
            created_by=self.alice,
            source="MANUAL",
        )

    def _make_prior_batch_row(self, description, amount, exp_date=None):
        if exp_date is None:
            # 400 days ago – well within the 730-day membership window
            exp_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        prior_batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.alice,
            original_filename="prior.csv",
            status="PENDING",
            total_rows=1,
        )
        ImportRow.objects.create(
            batch=prior_batch,
            row_number=1,
            raw_data={
                "date": exp_date,
                "description": description,
                "amount": str(amount),
                "currency": "INR",
                "paid_by": "alice@test.com",
                "participants": "alice@test.com,bob@test.com",
                "split_type": "equal",
            },
            status="PENDING",
        )
        return prior_batch

    # ── Production duplicates ──────────────────────────────────────────

    def test_exact_production_duplicate_flagged_as_warning(self):
        # Use a dynamic date that matches what _clean_row will produce
        match_date = date.today() - timedelta(days=400)
        self._make_production_expense(
            description="Dinner at restaurant", amount="1200", exp_date=match_date
        )
        row = self._make_row(self._clean_row(
            date=match_date.strftime("%Y-%m-%d"),
            description="Dinner at restaurant", amount="1200"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "DUPLICATE_EXPENSE").get()
        self.assertEqual(a.severity, "WARNING")
        self.assertEqual(a.metadata["source"], "production")

    def test_conflicting_production_amount_flagged_as_error(self):
        match_date = date.today() - timedelta(days=400)
        self._make_production_expense(
            description="Team lunch", amount="500", exp_date=match_date
        )
        row = self._make_row(self._clean_row(
            date=match_date.strftime("%Y-%m-%d"), description="Team lunch", amount="750"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "CONFLICTING_DUPLICATE").get()
        self.assertEqual(a.severity, "ERROR")
        self.assertEqual(a.metadata["source"], "production")
        # Decimal stored as string via str(Decimal), may include trailing zeros
        self.assertIn(a.metadata["existing_amount"], ["500", "500.00"])

    # ── Prior-batch duplicates ─────────────────────────────────────────

    def test_exact_prior_batch_duplicate_flagged(self):
        match_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        self._make_prior_batch_row("Coffee run", "150", exp_date=match_date)
        row = self._make_row(self._clean_row(
            date=match_date, description="Coffee run", amount="150"
        ))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "FLAGGED")
        a = self._anomalies_for(row, "DUPLICATE_EXPENSE").get()
        self.assertEqual(a.metadata["source"], "prior_batch")
        self.assertIn("prior_batch_id", a.metadata)
        self.assertIn("prior_row_number", a.metadata)

    def test_conflicting_prior_batch_amount_flagged(self):
        match_date = (date.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        self._make_prior_batch_row("Coffee run", "150", exp_date=match_date)
        row = self._make_row(self._clean_row(
            date=match_date, description="Coffee run", amount="200"
        ))
        self._set_total_rows(1)
        self._run()
        a = self._anomalies_for(row, "CONFLICTING_DUPLICATE").get()
        self.assertEqual(a.metadata["source"], "prior_batch")

    # ── Intra-batch duplicates ─────────────────────────────────────────

    def test_intra_batch_exact_duplicate_flagged(self):
        row1 = self._make_row(self._clean_row(date="2024-03-01", description="Coffee", amount="200"), row_number=1)
        row2 = self._make_row(self._clean_row(date="2024-03-01", description="Coffee", amount="200"), row_number=2)
        self._set_total_rows(2)
        self._run()
        row2.refresh_from_db()
        self.assertEqual(row2.status, "FLAGGED")
        a = self._anomalies_for(row2, "DUPLICATE_EXPENSE").get()
        self.assertEqual(a.metadata["source"], "intra_batch")
        self.assertEqual(a.metadata["duplicate_row"], 1)

    def test_intra_batch_conflicting_duplicate_flagged(self):
        row1 = self._make_row(self._clean_row(date="2024-03-01", description="Taxi", amount="300"), row_number=1)
        row2 = self._make_row(self._clean_row(date="2024-03-01", description="Taxi", amount="350"), row_number=2)
        self._set_total_rows(2)
        self._run()
        row2.refresh_from_db()
        self.assertEqual(row2.status, "FLAGGED")
        a = self._anomalies_for(row2, "CONFLICTING_DUPLICATE").get()
        self.assertEqual(a.metadata["source"], "intra_batch")

    def test_no_duplicate_new_expense(self):
        row = self._make_row(self._clean_row(
            description="Brand new unique expense XYZ123", amount="999"
        ))
        self._set_total_rows(1)
        self._run()
        self.assertFalse(
            ImportAnomaly.objects.filter(
                row=row, anomaly_type__in=["DUPLICATE_EXPENSE", "CONFLICTING_DUPLICATE"]
            ).exists()
        )


# ===========================================================================
# Row / Batch status transitions
# ===========================================================================

class StatusTransitionTests(AnomalyDetectionBase):

    def test_clean_row_status_becomes_approved(self):
        row = self._make_row(self._clean_row())
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        self.assertEqual(row.status, "APPROVED")

    def test_flagged_row_sets_batch_review_required(self):
        self._make_row(self._clean_row(amount="-1"))
        self._set_total_rows(1)
        self._run()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, "REVIEW_REQUIRED")

    def test_all_clean_rows_batch_stays_pending(self):
        self._make_row(self._clean_row(), row_number=1)
        self._make_row(self._clean_row(description="Another expense"), row_number=2)
        self._set_total_rows(2)
        result = self._run()
        self.assertEqual(result["batch_status"], "PENDING")
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, "PENDING")

    def test_mixed_batch_review_required(self):
        # Use a recent date and different descriptions to avoid intra-batch conflict
        recent = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        self._make_row(self._clean_row(date=recent, description="Team dinner"), row_number=1)  # clean
        self._make_row(self._clean_row(date=recent, description="Taxi ride", amount="-1"), row_number=2)  # flagged
        self._set_total_rows(2)
        result = self._run()
        self.assertEqual(result["rows_approved"], 1)
        self.assertEqual(result["rows_flagged"], 0)
        self.assertEqual(result["rows_rejected"], 1)
        self.assertEqual(result["batch_status"], "REVIEW_REQUIRED")

    def test_processing_notes_flagged_row(self):
        row = self._make_row(self._clean_row(amount="-1"))
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        joined = " ".join(row.processing_notes)
        self.assertIn("Rejected", joined)
        self.assertIn("NEGATIVE_AMOUNT", joined)

    def test_processing_notes_approved_row(self):
        row = self._make_row(self._clean_row())
        self._set_total_rows(1)
        self._run()
        row.refresh_from_db()
        joined = " ".join(row.processing_notes)
        self.assertIn("Approved", joined)

    def test_summary_dict_keys_present(self):
        self._make_row(self._clean_row())
        self._set_total_rows(1)
        result = self._run()
        for key in ("batch_id", "rows_processed", "rows_flagged", "rows_approved", "rows_rejected",
                    "anomalies_created", "batch_status"):
            self.assertIn(key, result)

    def test_summary_counts_correct(self):
        # Use different descriptions to prevent intra-batch conflict detection
        recent = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        self._make_row(self._clean_row(date=recent, description="Team dinner"), row_number=1)
        self._make_row(self._clean_row(date=recent, description="Taxi ride", amount="-1"), row_number=2)
        self._set_total_rows(2)
        result = self._run()
        self.assertEqual(result["rows_processed"], 2)
        self.assertEqual(result["rows_flagged"], 0)
        self.assertEqual(result["rows_rejected"], 1)
        self.assertEqual(result["rows_approved"], 1)
        self.assertGreaterEqual(result["anomalies_created"], 1)


# ===========================================================================
# Multiple anomalies on a single row
# ===========================================================================

class MultipleAnomalyTests(AnomalyDetectionBase):

    def test_single_row_can_have_multiple_anomalies(self):
        """A row with negative amount AND unknown currency → 2 anomalies."""
        row = self._make_row(self._clean_row(amount="-100", currency="XYZ"))
        self._set_total_rows(1)
        self._run()
        count = ImportAnomaly.objects.filter(row=row).count()
        self.assertGreaterEqual(count, 2)

    def test_single_row_negative_unknown_member_settlement(self):
        """Three rule violations on one row."""
        row = self._make_row(self._clean_row(
            amount="-1",
            paid_by="ghost@x.com",
            description="monthly settlement",
        ))
        self._set_total_rows(1)
        self._run()
        types = set(
            ImportAnomaly.objects.filter(row=row).values_list("anomaly_type", flat=True)
        )
        self.assertIn("NEGATIVE_AMOUNT", types)
        self.assertIn("UNKNOWN_MEMBER", types)
        self.assertIn("SETTLEMENT_AS_EXPENSE", types)


# ===========================================================================
# Detect API endpoint
# ===========================================================================

class AnomalyDetectAPITests(AnomalyDetectionBase):

    def _url(self, batch_id=None):
        bid = batch_id or self.batch.id
        return f"/api/imports/{bid}/detect/"

    def test_authenticated_member_gets_200(self):
        self._make_row(self._clean_row())
        self._set_total_rows(1)
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("batch_id", response.data)
        self.assertIn("rows_processed", response.data)
        self.assertIn("batch_status", response.data)

    def test_unauthenticated_request_rejected_401(self):
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 401)

    def test_nonexistent_batch_returns_404(self):
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(self._url(batch_id=uuid.uuid4()))
        self.assertEqual(response.status_code, 404)

    def test_non_member_non_uploader_forbidden_403(self):
        non_member = make_user("nm", "nm@test.com")
        self.client.force_authenticate(user=non_member)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 403)

    def test_response_includes_anomaly_counts(self):
        self._make_row(self._clean_row(amount="-1"))
        self._set_total_rows(1)
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["anomalies_created"], 1)
        self.assertEqual(response.data["batch_status"], "REVIEW_REQUIRED")

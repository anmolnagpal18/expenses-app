from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from groups.models import Group, Membership
from expenses.models import Settlement, Expense, BalanceSnapshot, StaticExchangeRate
from expenses.services import ExpenseService, SettlementService
from expenses.balance_engine import BalanceEngine

User = get_user_model()

class SettlementAPITests(APITestCase):
    def setUp(self):
        # Create users
        self.user_a = User.objects.create_user(
            username='usera', email='usera@gmail.com', full_name='User A', password='Password123'
        )
        self.user_b = User.objects.create_user(
            username='userb', email='userb@gmail.com', full_name='User B', password='Password123'
        )
        self.user_c = User.objects.create_user(
            username='userc', email='userc@gmail.com', full_name='User C', password='Password123'
        )
        self.non_member = User.objects.create_user(
            username='nonmember', email='nonmember@gmail.com', full_name='Non Member', password='Password123'
        )

        # Create group
        self.group = Group.objects.create(
            name='Settlement Group', base_currency='INR', created_by=self.user_a
        )

        # Create active memberships (joined 20 days ago)
        self.membership_a = Membership.objects.create(
            group=self.group, user=self.user_a, role='OWNER', joined_at=timezone.now() - timedelta(days=20)
        )
        self.membership_b = Membership.objects.create(
            group=self.group, user=self.user_b, role='MEMBER', joined_at=timezone.now() - timedelta(days=20)
        )

        # Static Exchange Rate USD -> INR
        StaticExchangeRate.objects.create(
            from_currency='USD', to_currency='INR', rate=Decimal('80.0000')
        )

        # Endpoint URLs
        self.create_url = reverse('settlement-create')

    # --- Settlement Creation ---

    def test_create_settlement_success(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify database
        self.assertEqual(Settlement.objects.count(), 1)
        settlement = Settlement.objects.first()
        self.assertEqual(settlement.original_amount, Decimal('50.00'))
        self.assertEqual(settlement.converted_amount, Decimal('50.00'))
        self.assertEqual(settlement.currency, 'INR')
        self.assertEqual(settlement.exchange_rate, Decimal('1.0000'))
        self.assertEqual(settlement.from_user, self.user_b)
        self.assertEqual(settlement.to_user, self.user_a)

        # Verify Response details
        self.assertEqual(response.data['id'], str(settlement.id))
        self.assertEqual(response.data['payer']['id'], self.user_b.id)
        self.assertEqual(response.data['receiver']['id'], self.user_a.id)
        self.assertEqual(response.data['converted_amount'], '50.00')
        self.assertEqual(response.data['exchange_rate'], '1.0000')

    def test_create_settlement_unauthenticated(self):
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_settlement_non_group_member_rejected(self):
        self.client.force_authenticate(user=self.non_member)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        # Blocked by IsGroupMember permission class
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_settlement_historical_member_allowed(self):
        # User C joins, leaves, and has historical membership (joined day -20, left day -10)
        Membership.objects.create(
            group=self.group, user=self.user_c, role='MEMBER',
            joined_at=timezone.now() - timedelta(days=20),
            left_at=timezone.now() - timedelta(days=10)
        )

        self.client.force_authenticate(user=self.user_a)
        # Settle on day -15 (valid active period for C)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_c.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today() - timedelta(days=15))
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_settlement_unsupported_currency_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'CAD', # Unsupported currency
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('currency', response.data)

    # --- Validations ---

    def test_validation_amount_non_positive_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '-10.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.data)

    def test_validation_self_settlement_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_a.id,
            'to_user_id': self.user_a.id, # from == to
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_invalid_group_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': '00000000-0000-0000-0000-000000000000',
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('group_id', response.data)

    def test_validation_invalid_user_rejected(self):
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': 999999,
            'to_user_id': self.user_a.id,
            'amount': '50.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('from_user_id', response.data)

    # --- Balance Engine & Snapshots Integration ---

    def test_balance_engine_and_snapshot_lifecycle(self):
        # 1. Establish initial debt: A pays 150, split equally A, B, C (50 each)
        # User C joins group as active member
        Membership.objects.create(
            group=self.group, user=self.user_c, role='MEMBER', joined_at=timezone.now() - timedelta(days=20)
        )

        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Dinner', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Initial snapshots check: B owes A 50, C owes A 50
        snapshots = BalanceSnapshot.objects.filter(group=self.group)
        self.assertEqual(snapshots.count(), 2)
        snap_b = snapshots.get(from_user=self.user_b)
        self.assertEqual(snap_b.balance, Decimal('50.00'))
        self.assertEqual(snap_b.calculation_version, 1)

        # 2. Partial Settlement: B settles 30 INR to A
        self.client.force_authenticate(user=self.user_a)
        payload_partial = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '30.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload_partial, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check refreshed snapshots: B owes A 20 now (50 - 30)
        snapshots_refreshed = BalanceSnapshot.objects.filter(group=self.group)
        self.assertEqual(snapshots_refreshed.count(), 2)
        snap_b_new = snapshots_refreshed.get(from_user=self.user_b)
        self.assertEqual(snap_b_new.balance, Decimal('20.00'))

        # Check BalanceEngine values directly
        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        self.assertEqual(b_to_a["amount"], Decimal('20.00'))

        # 3. Full Settlement: B settles remaining 20 INR to A
        payload_full = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '20.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload_full, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check refreshed snapshots: B owes A is cleared (only C owes A 50 remains)
        snapshots_final = BalanceSnapshot.objects.filter(group=self.group)
        self.assertEqual(snapshots_final.count(), 1)
        self.assertFalse(snapshots_final.filter(from_user=self.user_b).exists())

        # Check BalanceEngine directly
        balances_final = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a_final = next((b for b in balances_final if b["from_user_id"] == self.user_b.id), None)
        self.assertIsNone(b_to_a_final)

        # 4. Overpayment (Cannot create reverse debt): B settles 20 INR to A again
        payload_over = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '20.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload_over, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify that B does not owe A, and A does not owe B (balance capped at 0.00)
        balances_over = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a_over = next((b for b in balances_over if b["from_user_id"] == self.user_b.id or b["from_user_id"] == self.user_a.id), None)
        self.assertIsNone(b_to_a_over)

    # --- Settlement Detail View ---

    def test_settlement_detail_endpoint(self):
        # Create a settlement
        settlement = Settlement.objects.create(
            group=self.group, from_user=self.user_b, to_user=self.user_a,
            original_amount=Decimal('45.00'), converted_amount=Decimal('45.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )
        detail_url = reverse('settlement-detail', kwargs={'id': settlement.id})

        # 1. Group member can access detail
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(settlement.id))
        self.assertEqual(response.data['payer']['username'], 'userb')
        self.assertEqual(response.data['receiver']['username'], 'usera')

        # 2. Non-group member denied access
        self.client.force_authenticate(user=self.non_member)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Soft-deleted settlement hidden
        settlement.is_deleted = True
        settlement.deleted_at = timezone.now()
        settlement.save()

        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Explanation Engine ---

    def test_explanation_engine_integration(self):
        # Establish debt: A pays 150, split equally A, B, C (50 each)
        Membership.objects.create(
            group=self.group, user=self.user_c, role='MEMBER', joined_at=timezone.now() - timedelta(days=20)
        )
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Create a settlement: B settles 30 INR to A
        self.client.force_authenticate(user=self.user_a)
        payload = {
            'group_id': str(self.group.id),
            'from_user_id': self.user_b.id,
            'to_user_id': self.user_a.id,
            'amount': '30.00',
            'currency': 'INR',
            'settlement_date': str(date.today())
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        settlement_id = response.data['id']

        # Verify explanation
        explanation = BalanceEngine.get_balance_explanation(self.group.id, self.user_b.id, self.user_a.id)
        self.assertEqual(explanation["balance"], Decimal('20.00'))
        
        # Check expense breakdown contains the lunch split
        self.assertEqual(len(explanation["expense_breakdown"]), 1)
        self.assertEqual(explanation["expense_breakdown"][0]["amount"], Decimal('50.00'))

        # Check settlement breakdown contains the new settlement
        self.assertEqual(len(explanation["settlement_breakdown"]), 1)
        self.assertEqual(str(explanation["settlement_breakdown"][0]["settlement_id"]), settlement_id)
        self.assertEqual(explanation["settlement_breakdown"][0]["amount"], Decimal('30.00'))

        # Math invariant: balance = sum(expenses) - sum(settlements)
        exp_sum = sum(e["amount"] for e in explanation["expense_breakdown"])
        setl_sum = sum(s["amount"] for s in explanation["settlement_breakdown"])
        self.assertEqual(explanation["balance"], exp_sum - setl_sum)

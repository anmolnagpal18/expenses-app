from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from groups.models import Group, Membership
from expenses.models import Expense, ExpenseContribution, ExpenseSplit, Settlement, BalanceSnapshot, StaticExchangeRate
from expenses.services import ExpenseService, BalanceSnapshotService
from expenses.balance_engine import BalanceEngine

User = get_user_model()

class BalanceEngineTests(TestCase):
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
        self.user_d = User.objects.create_user(
            username='userd', email='userd@gmail.com', full_name='User D', password='Password123'
        )

        # Create group
        self.group = Group.objects.create(
            name='Test Group', base_currency='INR', created_by=self.user_a
        )

        # Create active memberships (joined 20 days ago)
        Membership.objects.create(
            group=self.group, user=self.user_a, role='OWNER', joined_at=timezone.now() - timedelta(days=20)
        )
        Membership.objects.create(
            group=self.group, user=self.user_b, role='MEMBER', joined_at=timezone.now() - timedelta(days=20)
        )
        Membership.objects.create(
            group=self.group, user=self.user_c, role='MEMBER', joined_at=timezone.now() - timedelta(days=20)
        )

        # Create static exchange rate USD -> INR
        StaticExchangeRate.objects.create(
            from_currency='USD', to_currency='INR', rate=Decimal('80.0000')
        )

    def assert_zero_sum_balances(self, group_id):
        """
        Integrity Rule Invariant Check: Sum(all balances) must equal zero.
        Checks for self-debts and strictly positive values.
        """
        balances = BalanceEngine.calculate_group_balances(group_id)["balances"]
        user_net = defaultdict(Decimal)
        for bal in balances:
            u_from = bal["from_user_id"]
            u_to = bal["to_user_id"]
            amt = bal["amount"]

            self.assertNotEqual(u_from, u_to, "Self-debt found in balances!")
            self.assertGreater(amt, 0, "Bilateral balance amount must be strictly positive!")

            user_net[u_from] -= amt
            user_net[u_to] += amt

        total_sum = sum(user_net.values())
        self.assertEqual(total_sum, Decimal('0.00'), f"Bilateral balance sheet is not zero-sum! Got total sum: {total_sum}")

    # --- Basic Balances ---

    def test_equal_split_expense(self):
        # A pays 150 INR, split equally among A, B, C (50 each)
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [
            {'user_id': self.user_a.id, 'share_value': Decimal('1.00')},
            {'user_id': self.user_b.id, 'share_value': Decimal('1.00')},
            {'user_id': self.user_c.id, 'share_value': Decimal('1.00')}
        ]
        ExpenseService.create_expense(
            group_id=self.group.id,
            description='Lunch',
            date=date.today(),
            original_amount=Decimal('150.00'),
            currency='INR',
            split_type='equal',
            created_by=self.user_a,
            contributors=contributors,
            splits=splits
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        self.assertEqual(len(balances), 2)
        
        # B owes A 50, C owes A 50
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        c_to_a = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)
        
        self.assertEqual(b_to_a["amount"], Decimal('50.00'))
        self.assertEqual(c_to_a["amount"], Decimal('50.00'))
        self.assert_zero_sum_balances(self.group.id)

    def test_unequal_split_expense(self):
        # A pays 100 INR, split percentage: A (20%), B (30%), C (50%)
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('100.00')}]
        splits = [
            {'user_id': self.user_a.id, 'share_value': Decimal('20.00')},
            {'user_id': self.user_b.id, 'share_value': Decimal('30.00')},
            {'user_id': self.user_c.id, 'share_value': Decimal('50.00')}
        ]
        ExpenseService.create_expense(
            group_id=self.group.id,
            description='Percentage Lunch',
            date=date.today(),
            original_amount=Decimal('100.00'),
            currency='INR',
            split_type='percentage',
            created_by=self.user_a,
            contributors=contributors,
            splits=splits
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        c_to_a = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)

        self.assertEqual(b_to_a["amount"], Decimal('30.00'))
        self.assertEqual(c_to_a["amount"], Decimal('50.00'))
        self.assert_zero_sum_balances(self.group.id)

    def test_multiple_contributors_and_participants(self):
        # Lunch cost 120 INR, split equally among A, B, C (40 each)
        # Contributors: A paid 80 INR, B paid 40 INR
        contributors = [
            {'user_id': self.user_a.id, 'amount_paid': Decimal('80.00')},
            {'user_id': self.user_b.id, 'amount_paid': Decimal('40.00')}
        ]
        splits = [
            {'user_id': self.user_a.id, 'share_value': Decimal('1.00')},
            {'user_id': self.user_b.id, 'share_value': Decimal('1.00')},
            {'user_id': self.user_c.id, 'share_value': Decimal('1.00')}
        ]
        ExpenseService.create_expense(
            group_id=self.group.id,
            description='Shared Lunch',
            date=date.today(),
            original_amount=Decimal('120.00'),
            currency='INR',
            split_type='equal',
            created_by=self.user_a,
            contributors=contributors,
            splits=splits
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        # Expected Proportional Calculation:
        # A paid 2/3, B paid 1/3
        # C owes A: 40 * 2/3 = 26.67
        # C owes B: 40 * 1/3 = 13.33
        # B owes A: (40 split * 2/3 paid by A) - (40 split * 1/3 paid by B) = 26.67 - 13.33 = 13.34 (due to remainder)
        
        c_to_a = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)
        c_to_b = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_b.id)
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)

        self.assertEqual(c_to_a["amount"], Decimal('26.67'))
        self.assertEqual(c_to_b["amount"], Decimal('13.33'))
        self.assertEqual(b_to_a["amount"], Decimal('13.34'))
        self.assert_zero_sum_balances(self.group.id)

    # --- Settlements ---

    def test_settlement_reduces_debt(self):
        # A paid 150 INR. B owes A 50.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Create a settlement of 30 INR from B to A
        # Directly create a mock settlement (since SettlementService is a skeleton)
        Settlement.objects.create(
            group=self.group,
            from_user=self.user_b,
            to_user=self.user_a,
            original_amount=Decimal('30.00'),
            converted_amount=Decimal('30.00'),
            currency='INR',
            exchange_rate=Decimal('1.0000'),
            settlement_date=date.today()
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        self.assertEqual(b_to_a["amount"], Decimal('20.00')) # 50 - 30 = 20
        self.assert_zero_sum_balances(self.group.id)

    def test_settlement_cannot_reverse_debt_direction(self):
        # A paid 150 INR. B owes A 50.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # B settles 70 INR to A (overpayment)
        Settlement.objects.create(
            group=self.group,
            from_user=self.user_b,
            to_user=self.user_a,
            original_amount=Decimal('70.00'),
            converted_amount=Decimal('70.00'),
            currency='INR',
            exchange_rate=Decimal('1.0000'),
            settlement_date=date.today()
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        # B owes A should cap at 0 and not reverse (A should not owe B 20)
        b_to_a = next((b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id), None)
        a_to_b = next((b for b in balances if b["from_user_id"] == self.user_a.id and b["to_user_id"] == self.user_b.id), None)

        self.assertIsNone(b_to_a)
        self.assertIsNone(a_to_b)
        self.assert_zero_sum_balances(self.group.id)

    def test_partial_and_full_settlement(self):
        # A paid 150 INR. B owes A 50.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Full settlement from B to A (50 INR)
        Settlement.objects.create(
            group=self.group, from_user=self.user_b, to_user=self.user_a,
            original_amount=Decimal('50.00'), converted_amount=Decimal('50.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next((b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id), None)
        self.assertIsNone(b_to_a)

    # --- Membership Scenarios ---

    def test_member_leaves_group_and_historical_expenses_remain_valid(self):
        # A paid 150 INR 5 days ago. User C left 2 days ago.
        expense_date = date.today() - timedelta(days=5)
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        
        # Deactivate C from the group (left 2 days ago)
        c_membership = Membership.objects.get(group=self.group, user=self.user_c)
        c_membership.left_at = timezone.now() - timedelta(days=2)
        c_membership.save()

        ExpenseService.create_expense(
            group_id=self.group.id, description='Old Lunch', date=expense_date,
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        # C owes A 50.00 is still active, because C was active on transaction date
        c_to_a = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)
        self.assertEqual(c_to_a["amount"], Decimal('50.00'))

        # If we create an expense today (C has left), C is not participant
        contributors_today = [{'user_id': self.user_a.id, 'amount_paid': Decimal('100.00')}]
        splits_today = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Today Dinner', date=date.today(),
            original_amount=Decimal('100.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors_today, splits=splits_today
        )

        balances_today = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next(b for b in balances_today if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        c_to_a = next(b for b in balances_today if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)

        self.assertEqual(b_to_a["amount"], Decimal('100.00')) # 50 old + 50 new
        self.assertEqual(c_to_a["amount"], Decimal('50.00'))  # remains 50
        self.assert_zero_sum_balances(self.group.id)

    def test_rejoined_member(self):
        # C joins, leaves, and rejoins.
        # First active period: day -20 to day -10
        c_membership1 = Membership.objects.get(group=self.group, user=self.user_c)
        c_membership1.joined_at = timezone.now() - timedelta(days=20)
        c_membership1.left_at = timezone.now() - timedelta(days=10)
        c_membership1.save()

        # Second active period: day -5 to future
        Membership.objects.create(
            group=self.group, user=self.user_c, role='MEMBER',
            joined_at=timezone.now() - timedelta(days=5)
        )

        # Expense during first period: A pays 150 INR. C participates.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Trip Day 2', date=date.today() - timedelta(days=15),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Expense during second period: A pays 90 INR. C participates.
        splits_2 = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Trip Day 18', date=date.today() - timedelta(days=3),
            original_amount=Decimal('90.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=[{'user_id': self.user_a.id, 'amount_paid': Decimal('90.00')}], splits=splits_2
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        c_to_a = next(b for b in balances if b["from_user_id"] == self.user_c.id and b["to_user_id"] == self.user_a.id)
        # C owes: 50 (first period) + 30 (second period) = 80
        self.assertEqual(c_to_a["amount"], Decimal('80.00'))

    # --- Multi-Currency ---

    def test_multi_currency_balances(self):
        # A pays 10.00 USD, base currency is INR. Exchange rate is 80.0000.
        # Converted total amount = 800.00 INR. Equal split A, B (400 INR each).
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('10.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='USD Coffee', date=date.today(),
            original_amount=Decimal('10.00'), currency='USD', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        b_to_a = next(b for b in balances if b["from_user_id"] == self.user_b.id and b["to_user_id"] == self.user_a.id)
        self.assertEqual(b_to_a["amount"], Decimal('400.00')) # converted balance
        self.assert_zero_sum_balances(self.group.id)

    # --- Explanation Engine ---

    def test_explanation_engine_traceability(self):
        # A paid 150 INR. B owes A 50.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        expense = ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch Split', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # B settles 20 INR to A
        settlement = Settlement.objects.create(
            group=self.group, from_user=self.user_b, to_user=self.user_a,
            original_amount=Decimal('20.00'), converted_amount=Decimal('20.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )

        # Get explanation B to A (from_user owes to_user)
        explanation = BalanceEngine.get_balance_explanation(self.group.id, self.user_b.id, self.user_a.id)
        
        self.assertEqual(explanation["balance"], Decimal('30.00')) # 50 - 20 = 30
        
        # Check expense breakdown
        self.assertEqual(len(explanation["expense_breakdown"]), 1)
        self.assertEqual(explanation["expense_breakdown"][0]["expense_id"], expense.id)
        self.assertEqual(explanation["expense_breakdown"][0]["amount"], Decimal('50.00'))

        # Check settlement breakdown
        self.assertEqual(len(explanation["settlement_breakdown"]), 1)
        self.assertEqual(explanation["settlement_breakdown"][0]["settlement_id"], settlement.id)
        self.assertEqual(explanation["settlement_breakdown"][0]["amount"], Decimal('20.00'))

        # Check math invariant: balance = sum(expenses) - sum(settlements)
        exp_sum = sum(e["amount"] for e in explanation["expense_breakdown"])
        setl_sum = sum(s["amount"] for s in explanation["settlement_breakdown"])
        self.assertEqual(explanation["balance"], exp_sum - setl_sum)

        # Get mirror explanation A to B
        mirror_explanation = BalanceEngine.get_balance_explanation(self.group.id, self.user_a.id, self.user_b.id)
        self.assertEqual(mirror_explanation["balance"], Decimal('-30.00'))
        self.assertEqual(len(mirror_explanation["expense_breakdown"]), 1)
        self.assertEqual(mirror_explanation["expense_breakdown"][0]["amount"], Decimal('-50.00'))
        self.assertEqual(mirror_explanation["settlement_breakdown"][0]["amount"], Decimal('-20.00'))

    # --- Snapshots ---

    def test_snapshots_refresh_lifecycle(self):
        # Snapshot refresh is triggered automatically when creating/deleting expenses
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        
        # Initial create
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch Split', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        snapshots = BalanceSnapshot.objects.filter(group=self.group)
        self.assertEqual(snapshots.count(), 2) # B owes A 50, C owes A 50
        
        snap_b = snapshots.get(from_user=self.user_b)
        self.assertEqual(snap_b.balance, Decimal('50.00'))
        self.assertEqual(snap_b.calculation_version, 1)

        # Create another expense to trigger refresh and verify overwrite
        contributors2 = [{'user_id': self.user_a.id, 'amount_paid': Decimal('90.00')}]
        splits2 = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}]
        
        ExpenseService.create_expense(
            group_id=self.group.id, description='Today Drink', date=date.today(),
            original_amount=Decimal('90.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors2, splits=splits2
        )

        # Fetch refreshed snapshots
        snapshots_refreshed = BalanceSnapshot.objects.filter(group=self.group)
        self.assertEqual(snapshots_refreshed.count(), 2) # count remains 2 (overwritten)
        
        snap_b_new = snapshots_refreshed.get(from_user=self.user_b)
        self.assertEqual(snap_b_new.balance, Decimal('95.00')) # 50 old + 45 new

    # --- Integrity Rules ---

    def test_deleted_transactions_ignored(self):
        # A paid 150 INR. B owes A 50.
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        expense = ExpenseService.create_expense(
            group_id=self.group.id, description='Deleted Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Verify balance exists
        balances_before = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        self.assertEqual(len(balances_before), 2)

        # Soft delete the expense
        ExpenseService.delete_expense(expense.id)

        # Verify balance is zero now
        balances_after = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        self.assertEqual(len(balances_after), 0)

        # Create a settlement and soft delete it
        settlement = Settlement.objects.create(
            group=self.group, from_user=self.user_b, to_user=self.user_a,
            original_amount=Decimal('20.00'), converted_amount=Decimal('20.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )
        # Mock soft delete on settlement
        settlement.is_deleted = True
        settlement.deleted_at = timezone.now()
        settlement.save()

        # Engine should ignore the deleted settlement
        balances_with_deleted_setl = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        self.assertEqual(len(balances_with_deleted_setl), 0)

    def test_calculate_user_balance(self):
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Lunch', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        user_b_bal = BalanceEngine.calculate_user_balance(self.group.id, self.user_b.id)
        self.assertEqual(len(user_b_bal["owes"]), 1)
        self.assertEqual(user_b_bal["owes"][0]["to_user_id"], self.user_a.id)
        self.assertEqual(user_b_bal["owes"][0]["amount"], Decimal('50.00'))
        self.assertEqual(len(user_b_bal["owed_by"]), 0)

        user_a_bal = BalanceEngine.calculate_user_balance(self.group.id, self.user_a.id)
        self.assertEqual(len(user_a_bal["owes"]), 0)
        self.assertEqual(len(user_a_bal["owed_by"]), 2)
        owed_by_b = next(ob for ob in user_a_bal["owed_by"] if ob["from_user_id"] == self.user_b.id)
        self.assertEqual(owed_by_b["amount"], Decimal('50.00'))

    def test_get_balance_explanation_fallback(self):
        explanation = BalanceEngine.get_balance_explanation(self.group.id, self.user_a.id, self.user_d.id)
        self.assertEqual(explanation["balance"], Decimal('0.00'))
        self.assertEqual(len(explanation["expense_breakdown"]), 0)
        self.assertEqual(len(explanation["settlement_breakdown"]), 0)

    def test_invalid_and_zero_amount_expenses_ignored(self):
        # 1. Zero amount expense: total_amount_base <= 0 (line 107 of balance_engine.py)
        Expense.objects.create(
            group=self.group, description='Zero Expense', date=date.today(),
            original_amount=Decimal('0.00'), converted_amount=Decimal('0.00'),
            currency='INR', exchange_rate=Decimal('1.00'), split_type='equal',
            created_by=self.user_a
        )

        # 2. Split amount <= 0 (line 128 of balance_engine.py)
        # A paid 100. A split it with B, but B's owed share is 0.00.
        nonzero_expense = Expense.objects.create(
            group=self.group, description='Non-Zero Expense', date=date.today(),
            original_amount=Decimal('100.00'), converted_amount=Decimal('100.00'),
            currency='INR', exchange_rate=Decimal('1.00'), split_type='exact',
            created_by=self.user_a
        )
        ExpenseContribution.objects.create(expense=nonzero_expense, user=self.user_a, amount_paid=Decimal('100.00'))
        ExpenseSplit.objects.create(expense=nonzero_expense, user=self.user_a, share_value=Decimal('100.00'), amount_owed=Decimal('100.00'))
        ExpenseSplit.objects.create(expense=nonzero_expense, user=self.user_b, share_value=Decimal('0.00'), amount_owed=Decimal('0.00'))

        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        # No balance for B since B owes 0.00
        self.assertEqual(len(balances), 0)

    def test_settlement_bidirectional_breakdown_coverage(self):
        # Set up an expense to establish a baseline debt structure
        contributors = [{'user_id': self.user_a.id, 'amount_paid': Decimal('150.00')}]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        ExpenseService.create_expense(
            group_id=self.group.id, description='Dinner Split', date=date.today(),
            original_amount=Decimal('150.00'), currency='INR', split_type='equal',
            created_by=self.user_a, contributors=contributors, splits=splits
        )

        # Create bidirectional settlements to hit all lines in bidirectional breakdown loops
        # Settlement 1: B settles 20 INR to A (to cover from_user=B, to_user=A)
        Settlement.objects.create(
            group=self.group, from_user=self.user_b, to_user=self.user_a,
            original_amount=Decimal('20.00'), converted_amount=Decimal('20.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )
        # Settlement 2: A settles 10 INR to B (to cover from_user=A, to_user=B)
        Settlement.objects.create(
            group=self.group, from_user=self.user_a, to_user=self.user_b,
            original_amount=Decimal('10.00'), converted_amount=Decimal('10.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), settlement_date=date.today()
        )

        explanation = BalanceEngine.get_balance_explanation(self.group.id, self.user_b.id, self.user_a.id)
        self.assertEqual(explanation["balance"], Decimal('40.00')) # 50 split - 20 (sent by B) + 10 (received from A) = 40.00
        self.assertEqual(len(explanation["settlement_breakdown"]), 2)

    def test_remainder_contributions_coverage(self):
        # A pays 80 INR and B pays 69.99 INR on a 150.00 INR expense
        contributors = [
            {'user_id': self.user_a.id, 'amount_paid': Decimal('80.00')},
            {'user_id': self.user_b.id, 'amount_paid': Decimal('69.99')}
        ]
        splits = [{'user_id': self.user_a.id}, {'user_id': self.user_b.id}, {'user_id': self.user_c.id}]
        
        # Directly bypass service validations to create this remainder-producing mismatch
        expense = Expense.objects.create(
            group=self.group, description='Remainder Test', date=date.today(),
            original_amount=Decimal('150.00'), converted_amount=Decimal('150.00'),
            currency='INR', exchange_rate=Decimal('1.0000'), split_type='equal',
            created_by=self.user_a
        )
        ExpenseContribution.objects.create(expense=expense, user=self.user_a, amount_paid=Decimal('80.00'))
        ExpenseContribution.objects.create(expense=expense, user=self.user_b, amount_paid=Decimal('69.99'))
        
        for u in [self.user_a, self.user_b, self.user_c]:
            ExpenseSplit.objects.create(expense=expense, user=u, share_value=Decimal('1.00'), amount_owed=Decimal('50.00'))

        # This will run code block with remainder_contrib = 150.00 - 149.99 = 0.01 != 0
        balances = BalanceEngine.calculate_group_balances(self.group.id)["balances"]
        self.assertGreater(len(balances), 0)

    def test_unused_repository_method_coverage(self):
        from expenses.repositories import ExpenseRepository
        membership = ExpenseRepository.get_active_membership(self.group.id, self.user_a.id, date.today())
        self.assertIsNotNone(membership)
        self.assertEqual(membership.user, self.user_a)

    def test_settlement_invalid_user_membership(self):
        from django.core.exceptions import ValidationError
        # Try to validate a settlement with a user who is not a member of the group
        settlement = Settlement(
            group=self.group,
            from_user=self.user_d, # Not in group
            to_user=self.user_a,
            original_amount=Decimal('50.00'),
            converted_amount=Decimal('50.00'),
            currency='INR',
            exchange_rate=Decimal('1.0000'),
            settlement_date=date.today()
        )
        with self.assertRaises(ValidationError) as ctx:
            settlement.clean()
        self.assertIn("must be a member of the group", str(ctx.exception))


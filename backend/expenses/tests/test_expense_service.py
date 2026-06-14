from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from groups.models import Group, Membership
from expenses.models import Expense, ExpenseContribution, ExpenseSplit, StaticExchangeRate
from expenses.services import ExpenseService

User = get_user_model()

class ExpenseServiceTests(TestCase):
    def setUp(self):
        # Create users
        self.creator = User.objects.create_user(
            username='creator', email='creator@gmail.com', full_name='Creator', password='Password123'
        )
        self.payer = User.objects.create_user(
            username='payer', email='payer@gmail.com', full_name='Payer', password='Password123'
        )
        self.participant = User.objects.create_user(
            username='participant', email='participant@gmail.com', full_name='Participant', password='Password123'
        )
        self.inactive_user = User.objects.create_user(
            username='inactive', email='inactive@gmail.com', full_name='Inactive', password='Password123'
        )

        # Create group
        self.group = Group.objects.create(
            name='Engine Group', base_currency='INR', created_by=self.creator
        )

        # Create memberships
        # Creator and Payer joined 10 days ago (active)
        Membership.objects.create(
            group=self.group, user=self.creator, role='OWNER', joined_at=timezone.now() - timedelta(days=10)
        )
        Membership.objects.create(
            group=self.group, user=self.payer, role='MEMBER', joined_at=timezone.now() - timedelta(days=10)
        )
        # Participant joined 5 days ago (active)
        Membership.objects.create(
            group=self.group, user=self.participant, role='MEMBER', joined_at=timezone.now() - timedelta(days=5)
        )
        # Inactive user joined 10 days ago, left 2 days ago (inactive today)
        Membership.objects.create(
            group=self.group, user=self.inactive_user, role='MEMBER',
            joined_at=timezone.now() - timedelta(days=10),
            left_at=timezone.now() - timedelta(days=2)
        )

        # Create exchange rate USD -> INR
        StaticExchangeRate.objects.create(
            from_currency='USD', to_currency='INR', rate=Decimal('80.0000')
        )

    # --- Successful Creation & Consistency ---

    def test_create_expense_success(self):
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')},
            {'user_id': self.participant.id, 'share_value': Decimal('1.00')}
        ]

        expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='Team Dinner',
            date=date.today(),
            original_amount=Decimal('100.00'),
            currency='INR',
            split_type='equal',
            created_by=self.creator,
            contributors=contributors,
            splits=splits,
            source='CSV_IMPORT'
        )

        self.assertIsNotNone(expense)
        self.assertEqual(expense.description, 'Team Dinner')
        self.assertEqual(expense.source, 'CSV_IMPORT')
        self.assertEqual(expense.converted_amount, Decimal('100.00')) # base currency INR
        self.assertEqual(expense.exchange_rate, Decimal('1.0000'))

        # Verifications
        contributions = ExpenseContribution.objects.filter(expense=expense)
        self.assertEqual(contributions.count(), 1)
        self.assertEqual(contributions.first().user, self.payer)
        self.assertEqual(contributions.first().amount_paid, Decimal('100.00'))

        expense_splits = ExpenseSplit.objects.filter(expense=expense)
        self.assertEqual(expense_splits.count(), 2)
        self.assertEqual(sum(s.amount_owed for s in expense_splits), Decimal('100.00'))
        self.assertEqual(expense_splits.filter(user=self.payer).first().amount_owed, Decimal('50.00'))

    # --- Membership Boundary Validation ---

    def test_create_expense_inactive_contributor_rejected(self):
        # Inactive user is a contributor -> rejected
        contributors = [
            {'user_id': self.inactive_user.id, 'amount_paid': Decimal('100.00')}
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')}
        ]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=self.creator,
                contributors=contributors,
                splits=splits
            )

    def test_create_expense_inactive_participant_rejected(self):
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}
        ]
        splits = [
            {'user_id': self.inactive_user.id, 'share_value': Decimal('1.00')}
        ]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=self.creator,
                contributors=contributors,
                splits=splits
            )

    def test_create_expense_creator_not_member_rejected(self):
        # unrelated creator user
        stranger = User.objects.create_user(
            username='stranger', email='stranger@gmail.com', full_name='Stranger', password='Password123'
        )
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')}
        ]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=stranger,
                contributors=contributors,
                splits=splits
            )

    # --- Contributor Total Validation ---

    def test_create_expense_contributor_total_mismatch_rejected(self):
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('90.00')} # Total paid 90, but total amount is 100
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')}
        ]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=self.creator,
                contributors=contributors,
                splits=splits
            )

    # --- Exchange Rate Currency Conversion ---

    def test_create_expense_usd_to_inr_conversion(self):
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('10.00')} # 10 USD
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')},
            {'user_id': self.participant.id, 'share_value': Decimal('1.00')}
        ]

        expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='USD Dinner',
            date=date.today(),
            original_amount=Decimal('10.00'),
            currency='USD',
            split_type='equal',
            created_by=self.creator,
            contributors=contributors,
            splits=splits
        )

        self.assertEqual(expense.converted_amount, Decimal('800.00')) # 10 USD * 80 rate = 800 INR
        self.assertEqual(expense.exchange_rate, Decimal('80.0000'))

        # Verifies amount_owed is converted to group base currency (INR)
        expense_splits = ExpenseSplit.objects.filter(expense=expense)
        self.assertEqual(expense_splits.count(), 2)
        # 5 USD each * 80 rate = 400 INR each
        self.assertEqual(expense_splits.first().amount_owed, Decimal('400.00'))

    # --- Atomic Transactions Rollback ---

    def test_create_expense_rollback_on_split_failure(self):
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')}
        ]
        
        # Mock create_split to raise an error
        with patch('expenses.repositories.ExpenseRepository.create_split', side_effect=Exception("Mock DB split error")):
            with self.assertRaises(Exception):
                ExpenseService.create_expense(
                    group_id=self.group.id,
                    description='Failed split rollback',
                    date=date.today(),
                    original_amount=Decimal('100.00'),
                    currency='INR',
                    split_type='equal',
                    created_by=self.creator,
                    contributors=contributors,
                    splits=splits
                )

        # Assert no expense was created in database
        self.assertEqual(Expense.objects.filter(description='Failed split rollback').count(), 0)

    def test_create_expense_invalid_group_rejected(self):
        import uuid
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        splits = [{'user_id': self.payer.id, 'share_value': Decimal('1.00')}]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=uuid.uuid4(),
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=self.creator,
                contributors=contributors,
                splits=splits
            )

    def test_create_expense_invalid_split_type_rejected(self):
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        splits = [{'user_id': self.payer.id, 'share_value': Decimal('1.00')}]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='invalid_type',
                created_by=self.creator,
                contributors=contributors,
                splits=splits
            )

    def test_create_expense_equal_split_list_of_ids(self):
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        # List of user IDs instead of dict/list-of-dict
        splits = [self.payer.id, self.participant.id]
        expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='Lunch',
            date=date.today(),
            original_amount=Decimal('100.00'),
            currency='INR',
            split_type='equal',
            created_by=self.creator,
            contributors=contributors,
            splits=splits
        )
        self.assertEqual(ExpenseSplit.objects.filter(expense=expense).count(), 2)

    def test_create_expense_equal_split_dict(self):
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        splits = {self.payer.id: Decimal('1.0')}
        expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='Lunch',
            date=date.today(),
            original_amount=Decimal('100.00'),
            currency='INR',
            split_type='equal',
            created_by=self.creator,
            contributors=contributors,
            splits=splits
        )
        self.assertEqual(ExpenseSplit.objects.filter(expense=expense).count(), 1)

    def test_create_expense_percentage_split_dict(self):
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        splits = {self.payer.id: Decimal('100.00')}
        expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='Lunch',
            date=date.today(),
            original_amount=Decimal('100.00'),
            currency='INR',
            split_type='percentage',
            created_by=self.creator,
            contributors=contributors,
            splits=splits
        )
        self.assertEqual(ExpenseSplit.objects.filter(expense=expense).count(), 1)

    def test_create_expense_invalid_splits_format(self):
        contributors = [{'user_id': self.payer.id, 'amount_paid': Decimal('100.00')}]
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='equal',
                created_by=self.creator,
                contributors=contributors,
                splits=123 # Invalid format
            )
        with self.assertRaises(ValidationError):
            ExpenseService.create_expense(
                group_id=self.group.id,
                description='Lunch',
                date=date.today(),
                original_amount=Decimal('100.00'),
                currency='INR',
                split_type='percentage',
                created_by=self.creator,
                contributors=contributors,
                splits=123 # Invalid format
            )

    def test_delete_non_existent_expense_rejected(self):
        import uuid
        with self.assertRaises(ValidationError):
            ExpenseService.delete_expense(uuid.uuid4())

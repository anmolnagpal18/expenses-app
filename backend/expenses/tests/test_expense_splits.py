from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from datetime import date
from groups.models import Group
from expenses.models import Expense, ExpenseSplit

User = get_user_model()

class ExpenseSplitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='splituser',
            email='split@gmail.com',
            full_name='Split User',
            password='Password123'
        )
        self.group = Group.objects.create(
            name='Test Group',
            base_currency='INR',
            created_by=self.user
        )
        self.expense = Expense.objects.create(
            group=self.group,
            description='Lunch',
            date=date.today(),
            original_amount=100.00,
            converted_amount=100.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='equal',
            created_by=self.user
        )

    def test_valid_split_creation(self):
        split = ExpenseSplit.objects.create(
            expense=self.expense,
            user=self.user,
            share_value=1.00,
            amount_owed=50.00
        )
        self.assertIsNotNone(split.id)
        self.assertEqual(split.amount_owed, 50.00)

    def test_amount_owed_non_negative_enforced(self):
        from django.db import transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseSplit.objects.create(
                    expense=self.expense,
                    user=self.user,
                    share_value=1.00,
                    amount_owed=-10.00
                )

        split = ExpenseSplit.objects.create(
            expense=self.expense,
            user=self.user,
            share_value=0.00,
            amount_owed=0.00
        )
        self.assertEqual(split.amount_owed, 0.00)

    def test_duplicate_split_rejected(self):
        from django.db import transaction
        ExpenseSplit.objects.create(
            expense=self.expense,
            user=self.user,
            share_value=1.00,
            amount_owed=25.00
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseSplit.objects.create(
                    expense=self.expense,
                    user=self.user,
                    share_value=1.00,
                    amount_owed=30.00
                )

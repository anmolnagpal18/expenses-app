from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from datetime import date
from groups.models import Group
from expenses.models import Expense, ExpenseContribution

User = get_user_model()

class ExpenseContributionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='contributor',
            email='contrib@gmail.com',
            full_name='Contrib User',
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

    def test_valid_contribution_creation(self):
        contrib = ExpenseContribution.objects.create(
            expense=self.expense,
            user=self.user,
            amount_paid=100.00
        )
        self.assertIsNotNone(contrib.id)
        self.assertEqual(contrib.amount_paid, 100.00)

    def test_amount_paid_positive_enforced(self):
        from django.db import transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseContribution.objects.create(
                    expense=self.expense,
                    user=self.user,
                    amount_paid=0.00
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseContribution.objects.create(
                    expense=self.expense,
                    user=self.user,
                    amount_paid=-50.00
                )

    def test_duplicate_contribution_rejected(self):
        from django.db import transaction
        ExpenseContribution.objects.create(
            expense=self.expense,
            user=self.user,
            amount_paid=50.00
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExpenseContribution.objects.create(
                    expense=self.expense,
                    user=self.user,
                    amount_paid=30.00
                )

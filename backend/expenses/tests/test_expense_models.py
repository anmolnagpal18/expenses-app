from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import date
from groups.models import Group
from expenses.models import Expense

User = get_user_model()

class ExpenseModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@gmail.com',
            full_name='Test User',
            password='Password123'
        )
        self.group = Group.objects.create(
            name='Trip Group',
            base_currency='INR',
            created_by=self.user
        )

    def test_valid_expense_creation(self):
        expense = Expense.objects.create(
            group=self.group,
            description='Dinner split',
            date=date.today(),
            original_amount=100.00,
            converted_amount=100.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='equal',
            created_by=self.user
        )
        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.source, 'MANUAL')
        self.assertFalse(expense.is_deleted)
        self.assertIsNone(expense.deleted_at)

    def test_uuid_generation(self):
        expense1 = Expense.objects.create(
            group=self.group,
            description='Expense 1',
            date=date.today(),
            original_amount=50.00,
            converted_amount=50.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='equal',
            created_by=self.user
        )
        expense2 = Expense.objects.create(
            group=self.group,
            description='Expense 2',
            date=date.today(),
            original_amount=60.00,
            converted_amount=60.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='equal',
            created_by=self.user
        )
        self.assertNotEqual(expense1.id, expense2.id)

    def test_supported_split_types(self):
        for split_type in ['equal', 'percentage', 'exact', 'shares']:
            expense = Expense(
                group=self.group,
                description=f'Test {split_type}',
                date=date.today(),
                original_amount=10.00,
                converted_amount=10.00,
                currency='INR',
                exchange_rate=1.0000,
                split_type=split_type,
                created_by=self.user
            )
            expense.full_clean()
            expense.save()

    def test_invalid_split_type_rejected(self):
        expense = Expense(
            group=self.group,
            description='Invalid split',
            date=date.today(),
            original_amount=10.00,
            converted_amount=10.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='invalid_type',
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            expense.full_clean()

    def test_soft_delete_works(self):
        expense = Expense.objects.create(
            group=self.group,
            description='Temporary expense',
            date=date.today(),
            original_amount=20.00,
            converted_amount=20.00,
            currency='INR',
            exchange_rate=1.0000,
            split_type='equal',
            created_by=self.user
        )
        self.assertFalse(expense.is_deleted)
        self.assertIsNone(expense.deleted_at)

        from expenses.services import ExpenseService
        ExpenseService.delete_expense(expense.id)
        
        expense.refresh_from_db()
        self.assertTrue(expense.is_deleted)
        self.assertIsNotNone(expense.deleted_at)

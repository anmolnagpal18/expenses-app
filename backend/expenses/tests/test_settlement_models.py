from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
from groups.models import Group, Membership
from expenses.models import Settlement

User = get_user_model()

class SettlementModelTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='usera',
            email='usera@gmail.com',
            full_name='User A',
            password='Password123'
        )
        self.user_b = User.objects.create_user(
            username='userb',
            email='userb@gmail.com',
            full_name='User B',
            password='Password123'
        )
        self.unrelated_user = User.objects.create_user(
            username='unrelated',
            email='unrelated@gmail.com',
            full_name='Unrelated User',
            password='Password123'
        )
        
        self.group = Group.objects.create(
            name='Travel Group',
            base_currency='INR',
            created_by=self.user_a
        )
        self.mem_a = Membership.objects.create(
            group=self.group,
            user=self.user_a,
            role='OWNER',
            joined_at=timezone.now() - timedelta(days=10)
        )
        self.mem_b = Membership.objects.create(
            group=self.group,
            user=self.user_b,
            role='MEMBER',
            joined_at=timezone.now() - timedelta(days=10),
            left_at=timezone.now() - timedelta(days=2)
        )

    def test_valid_settlement_creation(self):
        settlement = Settlement.objects.create(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            original_amount=100.00,
            converted_amount=100.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        self.assertIsNotNone(settlement.id)
        self.assertEqual(settlement.source, 'MANUAL')
        self.assertFalse(settlement.is_deleted)
        self.assertIsNone(settlement.deleted_at)

    def test_self_payment_rejected(self):
        settlement = Settlement(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_a,
            original_amount=50.00,
            converted_amount=50.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        with self.assertRaises(ValidationError):
            settlement.full_clean()

    def test_negative_or_zero_amount_rejected(self):
        settlement1 = Settlement(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            original_amount=0.00,
            converted_amount=0.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        with self.assertRaises(ValidationError):
            settlement1.full_clean()

        settlement2 = Settlement(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            original_amount=-5.00,
            converted_amount=-5.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        with self.assertRaises(ValidationError):
            settlement2.full_clean()

    def test_user_never_associated_with_group_rejected(self):
        settlement = Settlement(
            group=self.group,
            from_user=self.user_a,
            to_user=self.unrelated_user,
            original_amount=50.00,
            converted_amount=50.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        with self.assertRaises(ValidationError):
            settlement.full_clean()

    def test_soft_delete_fields_work(self):
        settlement = Settlement.objects.create(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            original_amount=10.00,
            converted_amount=10.00,
            currency='INR',
            exchange_rate=1.0000,
            settlement_date=date.today()
        )
        self.assertFalse(settlement.is_deleted)
        self.assertIsNone(settlement.deleted_at)

        settlement.is_deleted = True
        settlement.deleted_at = timezone.now()
        settlement.save()

        settlement.refresh_from_db()
        self.assertTrue(settlement.is_deleted)
        self.assertIsNotNone(settlement.deleted_at)

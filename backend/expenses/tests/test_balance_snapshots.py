from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from groups.models import Group
from expenses.models import BalanceSnapshot

User = get_user_model()

class BalanceSnapshotTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='snapshot_a',
            email='snap_a@gmail.com',
            full_name='Snap A',
            password='Password123'
        )
        self.user_b = User.objects.create_user(
            username='snapshot_b',
            email='snap_b@gmail.com',
            full_name='Snap B',
            password='Password123'
        )
        self.group = Group.objects.create(
            name='Snapshot Group',
            base_currency='INR',
            created_by=self.user_a
        )

    def test_valid_snapshot_creation(self):
        snap = BalanceSnapshot.objects.create(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            balance=150.75
        )
        self.assertIsNotNone(snap.id)
        self.assertEqual(snap.balance, 150.75)

    def test_unique_pair_per_group_enforced(self):
        from django.db import transaction
        BalanceSnapshot.objects.create(
            group=self.group,
            from_user=self.user_a,
            to_user=self.user_b,
            balance=50.00
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BalanceSnapshot.objects.create(
                    group=self.group,
                    from_user=self.user_a,
                    to_user=self.user_b,
                    balance=-10.00
                )

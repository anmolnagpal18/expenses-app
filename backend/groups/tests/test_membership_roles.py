from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from groups.models import Group, Membership

User = get_user_model()

class MembershipRoleTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password='Password@123'
        )
        self.other_user = User.objects.create_user(
            username='aisha',
            email='aisha@gmail.com',
            full_name='Aisha Patel',
            password='Password@123'
        )
        self.group = Group.objects.create(
            name='Flatmates',
            base_currency='INR',
            created_by=self.creator
        )
        # Create initial owner membership
        self.owner_membership = Membership.objects.create(
            group=self.group,
            user=self.creator,
            role='OWNER',
            joined_at=timezone.now() - timedelta(days=5)
        )

    def test_owner_creation(self):
        self.assertEqual(self.owner_membership.role, 'OWNER')

    def test_cannot_remove_last_owner(self):
        # Attempting to delete the only owner should raise ValidationError
        with self.assertRaises(ValidationError):
            self.owner_membership.delete()

        # Attempting to change role of only owner should raise ValidationError
        self.owner_membership.role = 'MEMBER'
        with self.assertRaises(ValidationError):
            self.owner_membership.save()

    def test_owner_transfer_allowed(self):
        # Create second membership with role OWNER
        new_owner = Membership.objects.create(
            group=self.group,
            user=self.other_user,
            role='OWNER',
            joined_at=timezone.now()
        )
        
        # Now we should be able to demote the first owner
        self.owner_membership.role = 'MEMBER'
        self.owner_membership.save() # should succeed now
        self.assertEqual(Membership.objects.filter(group=self.group, role='OWNER').count(), 1)
        self.assertEqual(Membership.objects.get(pk=self.owner_membership.pk).role, 'MEMBER')

    def test_multiple_admins_allowed(self):
        m1 = Membership.objects.create(
            group=self.group,
            user=self.other_user,
            role='ADMIN',
            joined_at=timezone.now()
        )
        third_user = User.objects.create_user(
            username='priya',
            email='priya@gmail.com',
            full_name='Priya Nair',
            password='Password@123'
        )
        m2 = Membership.objects.create(
            group=self.group,
            user=third_user,
            role='ADMIN',
            joined_at=timezone.now()
        )
        self.assertEqual(m1.role, 'ADMIN')
        self.assertEqual(m2.role, 'ADMIN')
        self.assertEqual(Membership.objects.filter(group=self.group, role='ADMIN').count(), 2)

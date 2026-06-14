from datetime import timedelta, datetime
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from groups.models import Group, Membership
from groups.repositories import MembershipRepository

User = get_user_model()

class MembershipValidationTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password='Password@123'
        )
        self.user = User.objects.create_user(
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
        # Create group OWNER membership to keep validations happy
        self.owner_membership = Membership.objects.create(
            group=self.group,
            user=self.creator,
            role='OWNER',
            joined_at=timezone.now() - timedelta(days=30)
        )

    def test_valid_membership_period(self):
        joined_at = timezone.now() - timedelta(days=10)
        left_at = timezone.now()
        membership = Membership(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=joined_at,
            left_at=left_at
        )
        membership.full_clean()
        membership.save()
        self.assertEqual(membership.joined_at, joined_at)
        self.assertEqual(membership.left_at, left_at)

    def test_left_at_before_joined_at_rejected(self):
        joined_at = timezone.now()
        left_at = timezone.now() - timedelta(days=5)
        membership = Membership(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=joined_at,
            left_at=left_at
        )
        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_overlapping_memberships_rejected(self):
        # Period 1: Jan 1 to Jan 31
        start1 = timezone.make_aware(datetime(2026, 1, 1))
        end1 = timezone.make_aware(datetime(2026, 1, 31))
        Membership.objects.create(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=start1,
            left_at=end1
        )
        
        # Period 2: Overlapping Jan 20 to Feb 10 (should fail)
        start2 = timezone.make_aware(datetime(2026, 1, 20))
        end2 = timezone.make_aware(datetime(2026, 2, 10))
        m2 = Membership(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=start2,
            left_at=end2
        )
        with self.assertRaises(ValidationError):
            m2.full_clean()

    def test_rejoin_after_leaving_allowed(self):
        # Period 1: Jan 1 to Jan 15
        start1 = timezone.make_aware(datetime(2026, 1, 1))
        end1 = timezone.make_aware(datetime(2026, 1, 15))
        Membership.objects.create(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=start1,
            left_at=end1
        )
        
        # Period 2: Disjoint Feb 1 to Feb 15 (should succeed)
        start2 = timezone.make_aware(datetime(2026, 2, 1))
        end2 = timezone.make_aware(datetime(2026, 2, 15))
        m2 = Membership(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=start2,
            left_at=end2
        )
        m2.full_clean()
        m2.save()
        self.assertEqual(Membership.objects.filter(group=self.group, user=self.user).count(), 2)

    def test_active_membership_lookup(self):
        # Open-ended active period from Jan 1
        start = timezone.make_aware(datetime(2026, 1, 1))
        membership = Membership.objects.create(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=start,
            left_at=None
        )
        
        # Lookup at Jan 10 -> active
        active_at_jan10 = MembershipRepository.get_active_membership_at(
            self.group.id, self.user.id, timezone.make_aware(datetime(2026, 1, 10))
        )
        self.assertIsNotNone(active_at_jan10)
        self.assertTrue(membership.is_active)

        # Lookup before joined -> inactive
        inactive_before = MembershipRepository.get_active_membership_at(
            self.group.id, self.user.id, timezone.make_aware(datetime(2025, 12, 31))
        )
        self.assertIsNone(inactive_before)

    def test_future_membership_is_inactive_now(self):
        # Period is set in the future
        future_start = timezone.now() + timedelta(days=10)
        membership = Membership.objects.create(
            group=self.group,
            user=self.user,
            role='MEMBER',
            joined_at=future_start
        )
        # Should be inactive right now
        self.assertFalse(membership.is_active)

    def test_membership_repository_get_by_id(self):
        import uuid
        fetched = MembershipRepository.get_by_id(self.owner_membership.id)
        self.assertEqual(fetched, self.owner_membership)
        self.assertIsNone(MembershipRepository.get_by_id(uuid.uuid4()))

    def test_membership_repository_get_group_memberships(self):
        memberships = MembershipRepository.get_group_memberships(self.group.id)
        self.assertIn(self.owner_membership, memberships)

        active = MembershipRepository.get_group_memberships(self.group.id, active_only=True)
        self.assertIn(self.owner_membership, active)

    def test_membership_repository_get_user_membership_in_group(self):
        m = MembershipRepository.get_user_membership_in_group(self.group.id, self.creator.id)
        self.assertIn(self.owner_membership, m)

    def test_membership_repository_check_overlap(self):
        # Already has owner_membership starting 30 days ago, open-ended
        start = timezone.now() - timedelta(days=10)
        has_overlap = MembershipRepository.check_overlap(self.group.id, self.creator.id, start)
        self.assertTrue(has_overlap)

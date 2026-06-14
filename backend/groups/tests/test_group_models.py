import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from groups.models import Group

User = get_user_model()

class GroupModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password='Password@123'
        )

    def test_group_creation_and_attributes(self):
        group = Group.objects.create(
            name='Room 404',
            base_currency='INR',
            created_by=self.user
        )
        self.assertEqual(group.name, 'Room 404')
        self.assertEqual(group.base_currency, 'INR')
        self.assertEqual(group.created_by, self.user)
        self.assertIsNotNone(group.created_at)
        
        # Verify auto-generated UUID primary key
        self.assertIsInstance(group.id, uuid.UUID)
        self.assertEqual(str(group), 'Room 404')

    def test_group_repository_get_by_id(self):
        from groups.repositories import GroupRepository
        group = Group.objects.create(
            name='Room 404',
            base_currency='INR',
            created_by=self.user
        )
        fetched = GroupRepository.get_by_id(group.id)
        self.assertEqual(fetched, group)
        
        # Non-existent UUID
        self.assertIsNone(GroupRepository.get_by_id(uuid.uuid4()))

    def test_group_repository_get_user_groups(self):
        from groups.repositories import GroupRepository
        from groups.models import Membership
        from django.utils import timezone
        
        group = Group.objects.create(
            name='Room 404',
            base_currency='INR',
            created_by=self.user
        )
        # Add a membership for the user
        Membership.objects.create(
            group=group,
            user=self.user,
            role='OWNER',
            joined_at=timezone.now()
        )
        groups = GroupRepository.get_user_groups(self.user)
        self.assertIn(group, groups)

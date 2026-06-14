from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APITestCase

from groups.models import Group, Membership

User = get_user_model()

class GroupAPITests(APITestCase):
    def setUp(self):
        # Create default users
        self.owner_user = User.objects.create_user(
            username='owner',
            email='owner@gmail.com',
            full_name='Group Owner',
            password='Password@123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@gmail.com',
            full_name='Group Admin',
            password='Password@123'
        )
        self.member_user = User.objects.create_user(
            username='member',
            email='member@gmail.com',
            full_name='Group Member',
            password='Password@123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@gmail.com',
            full_name='Unrelated User',
            password='Password@123'
        )
        self.new_user = User.objects.create_user(
            username='newuser',
            email='newuser@gmail.com',
            full_name='New User',
            password='Password@123'
        )

        # Create a group and memberships
        self.group = Group.objects.create(
            name='Test Group',
            base_currency='INR',
            created_by=self.owner_user
        )
        self.owner_membership = Membership.objects.create(
            group=self.group,
            user=self.owner_user,
            role='OWNER',
            joined_at=timezone.now() - timedelta(days=10)
        )
        self.admin_membership = Membership.objects.create(
            group=self.group,
            user=self.admin_user,
            role='ADMIN',
            joined_at=timezone.now() - timedelta(days=5)
        )
        self.member_membership = Membership.objects.create(
            group=self.group,
            user=self.member_user,
            role='MEMBER',
            joined_at=timezone.now() - timedelta(days=3)
        )

        # URLs
        self.list_create_url = reverse('group-list-create')
        self.detail_url = reverse('group-detail', kwargs={'id': self.group.id})
        self.add_member_url = reverse('add-member', kwargs={'id': self.group.id})

    # --- Group Creation ---

    def test_create_group_authenticated(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'name': 'New Adventure Group',
            'base_currency': 'USD'
        }
        response = self.client.post(self.list_create_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Adventure Group')
        self.assertEqual(response.data['base_currency'], 'USD')
        
        # Verify OWNER membership was automatically created
        new_group_id = response.data['id']
        memberships = Membership.objects.filter(group_id=new_group_id)
        self.assertEqual(memberships.count(), 1)
        self.assertEqual(memberships.first().user, self.owner_user)
        self.assertEqual(memberships.first().role, 'OWNER')

    def test_create_group_unauthenticated(self):
        payload = {
            'name': 'Unauthenticated Group'
        }
        response = self.client.post(self.list_create_url, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_group_invalid_currency(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'name': 'Unsupported Currency Group',
            'base_currency': 'JPY'  # JPY is not in supported list
        }
        response = self.client.post(self.list_create_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('base_currency', response.data)

    def test_create_group_default_currency(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'name': 'Default Currency Group'
        }
        response = self.client.post(self.list_create_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['base_currency'], 'INR')

    # --- Group List ---

    def test_list_groups_returns_joined_groups(self):
        # owner_user is in self.group
        self.client.force_authenticate(user=self.owner_user)
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.group.id))

    def test_list_groups_excludes_unrelated(self):
        # other_user has not joined any groups
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(self.list_create_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # --- Group Detail ---

    def test_retrieve_group_member_allowed(self):
        self.client.force_authenticate(user=self.member_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.group.id))
        self.assertEqual(len(response.data['memberships']), 3)

    def test_retrieve_group_non_member_denied(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Add Member ---

    def test_add_member_by_owner_success(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'email': 'newuser@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['email'], 'newuser@gmail.com')
        self.assertEqual(response.data['role'], 'MEMBER')
        
        # Verify saved in database
        self.assertTrue(Membership.objects.filter(group=self.group, user=self.new_user).exists())

    def test_add_member_by_admin_success(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'email': 'newuser@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_member_by_member_denied(self):
        self.client.force_authenticate(user=self.member_user)
        payload = {
            'email': 'newuser@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_member_duplicate_active_rejected(self):
        # member_user is already actively in the group
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'email': 'member@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should contain early validation error
        self.assertIn('email', response.data)

    def test_add_member_rejoin_allowed(self):
        self.client.force_authenticate(user=self.owner_user)
        
        # First, mark the member as left
        self.member_membership.left_at = timezone.now() - timedelta(days=1)
        self.member_membership.save()

        # Rejoin now (joined_at is current time)
        payload = {
            'email': 'member@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check that there are now two membership records
        self.assertEqual(Membership.objects.filter(group=self.group, user=self.member_user).count(), 2)

    def test_add_member_timeline_validation_error(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'email': 'newuser@gmail.com',
            'joined_at': timezone.now(),
            'left_at': timezone.now() - timedelta(days=1) # left_at before joined_at
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('left_at', response.data)

    def test_add_member_invalid_email(self):
        self.client.force_authenticate(user=self.owner_user)
        payload = {
            'email': 'nonexistent@gmail.com',
            'role': 'MEMBER'
        }
        response = self.client.post(self.add_member_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_placeholder_membership_endpoints(self):
        self.client.force_authenticate(user=self.owner_user)
        placeholder_url = reverse('membership-detail', kwargs={
            'group_id': self.group.id,
            'membership_id': self.member_membership.id
        })
        
        # Test PUT
        response = self.client.put(placeholder_url, {})
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        
        # Test PATCH
        response = self.client.patch(placeholder_url, {})
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        
        # Test DELETE
        response = self.client.delete(placeholder_url)
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)

    def test_membership_services_helpers(self):
        from groups.services import MembershipService
        from django.core.exceptions import ValidationError
        import uuid

        # Test set_member_left_date
        left_at_time = timezone.now()
        updated_membership = MembershipService.set_member_left_date(self.member_membership.id, left_at_time)
        self.assertEqual(updated_membership.left_at, left_at_time)

        # Test set_member_left_date invalid id
        with self.assertRaises(ValidationError):
            MembershipService.set_member_left_date(uuid.uuid4(), left_at_time)

        # Test change_member_role
        updated_membership = MembershipService.change_member_role(self.member_membership.id, 'ADMIN')
        self.assertEqual(updated_membership.role, 'ADMIN')

        # Test change_member_role invalid id
        with self.assertRaises(ValidationError):
            MembershipService.change_member_role(uuid.uuid4(), 'ADMIN')

    def test_permissions_edge_cases_and_owner_only(self):
        from groups.permissions import IsGroupOwner
        from rest_framework.test import APIRequestFactory
        from groups.views import GroupDetailView
        
        factory = APIRequestFactory()
        
        # Test IsGroupOwner has_permission
        permission = IsGroupOwner()
        
        # Owner request
        request = factory.get(self.detail_url)
        request.user = self.owner_user
        class DummyView:
            kwargs = {'id': self.group.id}
        self.assertTrue(permission.has_permission(request, DummyView()))
        
        # Non-owner request
        request = factory.get(self.detail_url)
        request.user = self.member_user
        self.assertFalse(permission.has_permission(request, DummyView()))

        # Request missing group_id
        class DummyViewNoKwargs:
            kwargs = {}
        self.assertFalse(permission.has_permission(request, DummyViewNoKwargs()))

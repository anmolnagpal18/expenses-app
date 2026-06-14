from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APITestCase

from groups.models import Group, Membership
from expenses.models import Expense, ExpenseContribution, ExpenseSplit, StaticExchangeRate
from expenses.services import ExpenseService

User = get_user_model()

class ExpenseAPITests(APITestCase):
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
        self.non_member = User.objects.create_user(
            username='nonmember', email='nonmember@gmail.com', full_name='Non Member', password='Password123'
        )

        # Create group
        self.group = Group.objects.create(
            name='Engine Group', base_currency='INR', created_by=self.creator
        )

        # Create memberships
        # Creator and Payer joined 10 days ago (active)
        self.creator_membership = Membership.objects.create(
            group=self.group, user=self.creator, role='OWNER', joined_at=timezone.now() - timedelta(days=10)
        )
        self.payer_membership = Membership.objects.create(
            group=self.group, user=self.payer, role='MEMBER', joined_at=timezone.now() - timedelta(days=10)
        )
        # Participant joined 5 days ago (active)
        self.participant_membership = Membership.objects.create(
            group=self.group, user=self.participant, role='MEMBER', joined_at=timezone.now() - timedelta(days=5)
        )
        # Inactive user joined 10 days ago, left 2 days ago (inactive today)
        self.inactive_membership = Membership.objects.create(
            group=self.group, user=self.inactive_user, role='MEMBER',
            joined_at=timezone.now() - timedelta(days=10),
            left_at=timezone.now() - timedelta(days=2)
        )

        # Create exchange rate USD -> INR
        self.rate = StaticExchangeRate.objects.create(
            from_currency='USD', to_currency='INR', rate=Decimal('80.0000')
        )

        # URLs
        self.create_url = reverse('expense-create')

        # Create a default expense for detail tests
        contributors = [
            {'user_id': self.payer.id, 'amount_paid': Decimal('150.00')}
        ]
        splits = [
            {'user_id': self.payer.id, 'share_value': Decimal('1.00')},
            {'user_id': self.participant.id, 'share_value': Decimal('1.00')}
        ]
        self.expense = ExpenseService.create_expense(
            group_id=self.group.id,
            description='Dinner Split',
            date=date.today(),
            original_amount=Decimal('150.00'),
            currency='USD',
            split_type='equal',
            created_by=self.creator,
            contributors=contributors,
            splits=splits,
            source='MANUAL'
        )
        self.detail_url = reverse('expense-detail', kwargs={'id': self.expense.id})

    # --- Expense Creation ---

    def test_create_expense_success(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Team Coffee',
            'date': str(date.today()),
            'original_amount': '150.00',
            'currency': 'USD',
            'split_type': 'equal',
            'contributors': [
                {
                    'user_id': str(self.payer.id),
                    'amount_paid': '150.00'
                }
            ],
            'participants': [
                {
                    'user_id': str(self.payer.id)
                },
                {
                    'user_id': str(self.participant.id)
                }
            ]
        }
        # Record initial counts
        expense_count = Expense.objects.count()
        contribution_count = ExpenseContribution.objects.count()
        split_count = ExpenseSplit.objects.count()

        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Data Integrity checks
        self.assertEqual(Expense.objects.count(), expense_count + 1)
        self.assertEqual(ExpenseContribution.objects.count(), contribution_count + 1)
        self.assertEqual(ExpenseSplit.objects.count(), split_count + 2)

        new_expense = Expense.objects.latest('created_at')
        self.assertEqual(new_expense.description, 'Team Coffee')
        self.assertEqual(new_expense.original_amount, Decimal('150.00'))
        # Converted amount stored correctly (150.00 * 80.0000 = 12000.00)
        self.assertEqual(new_expense.converted_amount, Decimal('12000.00'))
        self.assertEqual(new_expense.currency, 'USD')

        # Check detail serialization structure in response
        self.assertEqual(response.data['id'], str(new_expense.id))
        self.assertEqual(response.data['description'], 'Team Coffee')
        self.assertEqual(response.data['converted_amount'], '12000.00')
        self.assertEqual(response.data['created_by']['id'], self.creator.id)
        self.assertEqual(response.data['group']['id'], str(self.group.id))
        self.assertEqual(len(response.data['contributions']), 1)
        self.assertEqual(len(response.data['splits']), 2)

    def test_create_expense_unauthenticated(self):
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_expense_invalid_group(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': '00000000-0000-0000-0000-000000000000',
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('group_id', response.data)

    def test_create_expense_inactive_creator(self):
        # Create a user who left the group 2 days ago and try to authenticate
        inactive_creator = User.objects.create_user(
            username='inactive_creator', email='inc@gmail.com', full_name='Inc Creator', password='Password123'
        )
        Membership.objects.create(
            group=self.group, user=inactive_creator, role='MEMBER',
            joined_at=timezone.now() - timedelta(days=10),
            left_at=timezone.now() - timedelta(days=2)
        )
        self.client.force_authenticate(user=inactive_creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        # Membership validation helper in service blocks inactive members on the transaction date
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_inactive_participant(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.inactive_user.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_inactive_contributor(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.inactive_user.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Validations ---

    def test_create_expense_invalid_split_type(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'invalid_split_type',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('split_type', response.data)

    def test_create_expense_invalid_currency(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'CAD',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('currency', response.data)

    def test_create_expense_amount_less_than_or_equal_to_zero(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '0.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '0.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_contributors_required(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_participants_required(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '10.00'}],
            'participants': []
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_expense_contribution_totals_mismatch(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': str(self.payer.id), 'amount_paid': '12.00'}],
            'participants': [{'user_id': str(self.payer.id)}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Expense Detail ---

    def test_detail_endpoint_group_member_can_access(self):
        self.client.force_authenticate(user=self.payer)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check performance / nested structure requirements
        self.assertEqual(response.data['id'], str(self.expense.id))
        self.assertEqual(response.data['created_by']['username'], 'creator')
        self.assertEqual(response.data['group']['name'], 'Engine Group')
        
        # Nested contributions
        self.assertEqual(len(response.data['contributions']), 1)
        self.assertEqual(response.data['contributions'][0]['user']['username'], 'payer')
        self.assertEqual(response.data['contributions'][0]['amount_paid'], '150.00')

        # Nested splits
        self.assertEqual(len(response.data['splits']), 2)
        participants_emails = {s['user']['email'] for s in response.data['splits']}
        self.assertIn('payer@gmail.com', participants_emails)
        self.assertIn('participant@gmail.com', participants_emails)

    def test_detail_endpoint_non_member_denied(self):
        self.client.force_authenticate(user=self.non_member)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_endpoint_deleted_expense_hidden(self):
        self.client.force_authenticate(user=self.payer)
        # Soft delete the expense
        self.expense.is_deleted = True
        self.expense.deleted_at = timezone.now()
        self.expense.save()

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Additional coverage tests for permissions and edge-case errors ---

    def test_create_expense_non_existent_contributor(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': 999999, 'amount_paid': '10.00'}],
            'participants': [{'user_id': self.payer.id}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('contributors', response.data)

    def test_create_expense_non_existent_participant(self):
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': self.payer.id, 'amount_paid': '10.00'}],
            'participants': [{'user_id': 999999}]
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('participants', response.data)

    def test_permission_class_direct_checks(self):
        from expenses.permissions import IsGroupMember
        from unittest.mock import MagicMock

        permission = IsGroupMember()

        # 1. Unauthenticated request
        req_unauth = MagicMock()
        req_unauth.user.is_authenticated = False
        self.assertFalse(permission.has_permission(req_unauth, MagicMock()))

        # 2. Detail view with malformed or non-existent expense ID
        req_auth = MagicMock()
        req_auth.user = self.payer
        
        view_invalid_uuid = MagicMock()
        view_invalid_uuid.kwargs = {'id': 'invalid-uuid'}
        self.assertFalse(permission.has_permission(req_auth, view_invalid_uuid))

        # 3. Create view (no ID in kwargs) with missing group_id in request.data
        view_no_kwargs = MagicMock()
        view_no_kwargs.kwargs = {}
        req_no_group = MagicMock()
        req_no_group.user = self.payer
        req_no_group.data = {}
        self.assertFalse(permission.has_permission(req_no_group, view_no_kwargs))

        # 4. Create view with group_id where user is active member
        req_with_group = MagicMock()
        req_with_group.user = self.payer
        req_with_group.data = {'group_id': str(self.group.id)}
        self.assertTrue(permission.has_permission(req_with_group, view_no_kwargs))

    def test_views_custom_validation_error(self):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from unittest.mock import patch
        
        self.client.force_authenticate(user=self.creator)
        payload = {
            'group_id': str(self.group.id),
            'description': 'Coffee',
            'date': str(date.today()),
            'original_amount': '10.00',
            'currency': 'INR',
            'split_type': 'equal',
            'contributors': [{'user_id': self.payer.id, 'amount_paid': '10.00'}],
            'participants': [{'user_id': self.payer.id}]
        }

        # Mock create_expense to raise custom Django ValidationError with messages list
        with patch('expenses.services.ExpenseService.create_expense') as mock_create:
            mock_create.side_effect = DjangoValidationError(message=['Error 1', 'Error 2'])
            response = self.client.post(self.create_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data['detail'], ['Error 1', 'Error 2'])

        # Mock create_expense to raise standard Python string ValidationError without messages or message_dict attributes
        class CustomValidationError(DjangoValidationError):
            def __init__(self):
                pass
            def __str__(self):
                return "Fallback error"
            @property
            def messages(self):
                raise AttributeError("No messages")
            @property
            def message_dict(self):
                raise AttributeError("No message_dict")

        with patch('expenses.services.ExpenseService.create_expense') as mock_create:
            mock_create.side_effect = CustomValidationError()
            response = self.client.post(self.create_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data['detail'], 'Fallback error')


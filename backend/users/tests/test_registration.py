from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()

class RegistrationTests(APITestCase):
    def setUp(self):
        self.signup_url = reverse('signup')
        self.valid_payload = {
            'username': 'aisha',
            'email': 'aisha@gmail.com',
            'full_name': 'Aisha Patel',
            'password': 'Password@123',
            'password_confirm': 'Password@123'
        }

    def test_successful_registration(self):
        response = self.client.post(self.signup_url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'aisha@gmail.com')
        self.assertEqual(response.data['user']['full_name'], 'Aisha Patel')
        
        # Verify db persistence & email normalization to lowercase/stripped
        user = User.objects.get(username='aisha')
        self.assertEqual(user.email, 'aisha@gmail.com')
        self.assertEqual(user.full_name, 'Aisha Patel')

    def test_email_normalization_on_registration(self):
        payload = self.valid_payload.copy()
        payload['email'] = '  AISHA@GMAIL.COM  '
        response = self.client.post(self.signup_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify normalization
        user = User.objects.get(username='aisha')
        self.assertEqual(user.email, 'aisha@gmail.com')

    def test_password_mismatch(self):
        payload = self.valid_payload.copy()
        payload['password_confirm'] = 'DifferentPassword@123'
        response = self.client.post(self.signup_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_duplicate_email_prevention(self):
        # Register a user first
        User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password='Password@123'
        )
        
        # Attempt duplicate email signup
        payload = self.valid_payload.copy()
        payload['email'] = 'rohan@gmail.com'
        payload['username'] = 'rohan2'
        response = self.client.post(self.signup_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_duplicate_email_case_insensitive_prevention(self):
        # Register a user first
        User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password='Password@123'
        )
        
        # Attempt uppercase duplicate email signup
        payload = self.valid_payload.copy()
        payload['email'] = 'ROHAN@GMAIL.COM'
        payload['username'] = 'rohan2'
        response = self.client.post(self.signup_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_missing_required_fields(self):
        required_fields = ['username', 'email', 'full_name', 'password', 'password_confirm']
        for field in required_fields:
            payload = self.valid_payload.copy()
            payload.pop(field)
            response = self.client.post(self.signup_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(field, response.data)

from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()

class LoginTests(APITestCase):
    def setUp(self):
        self.login_url = reverse('login')
        self.refresh_url = reverse('token_refresh')
        self.user_password = 'Password@123'
        self.user = User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password=self.user_password
        )

    def test_successful_login(self):
        # Authenticate using email and password
        payload = {
            'email': 'rohan@gmail.com',
            'password': self.user_password
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], 'rohan@gmail.com')

    def test_login_email_case_insensitivity(self):
        # Verify that logging in with uppercase email works since they normalize
        payload = {
            'email': 'ROHAN@GMAIL.COM',
            'password': self.user_password
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_password(self):
        payload = {
            'email': 'rohan@gmail.com',
            'password': 'WrongPassword123'
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', response.data)

    def test_nonexistent_user(self):
        payload = {
            'email': 'nonexistent@gmail.com',
            'password': self.user_password
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        payload = {
            'email': 'rohan@gmail.com',
            'password': self.user_password
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_token_refresh(self):
        # Login to get refresh token
        payload = {
            'email': 'rohan@gmail.com',
            'password': self.user_password
        }
        login_response = self.client.post(self.login_url, payload, format='json')
        refresh_token = login_response.data['refresh']

        # Refresh the access token
        refresh_payload = {
            'refresh': refresh_token
        }
        response = self.client.post(self.refresh_url, refresh_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_jwt_token_refresh_invalid_token(self):
        refresh_payload = {
            'refresh': 'invalid_refresh_token_value'
        }
        response = self.client.post(self.refresh_url, refresh_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

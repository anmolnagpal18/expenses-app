from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()

class ProfileTests(APITestCase):
    def setUp(self):
        self.profile_url = reverse('profile')
        self.user_password = 'Password@123'
        self.user = User.objects.create_user(
            username='rohan',
            email='rohan@gmail.com',
            full_name='Rohan Sharma',
            password=self.user_password
        )

    def test_authenticated_profile_access(self):
        # Authenticate first
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'rohan@gmail.com')
        self.assertEqual(response.data['full_name'], 'Rohan Sharma')
        self.assertEqual(response.data['username'], 'rohan')

    def test_unauthenticated_profile_access(self):
        # Access profile without credentials
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

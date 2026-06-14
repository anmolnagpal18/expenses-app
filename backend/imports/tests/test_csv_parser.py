import io
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta

from groups.models import Group, Membership
from imports.models import ImportBatch, ImportRow, ImportAnomaly
from imports.services import CSVImportService

User = get_user_model()

class CSVParserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='parser_user', email='parser@gmail.com', password='Password123'
        )
        self.group = Group.objects.create(
            name='Test Parser Group', base_currency='INR', created_by=self.user
        )
        self.batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.user,
            original_filename='test.csv'
        )

    # --- Header Validation Tests ---

    def test_header_validation_success_standard_headers(self):
        csv_data = (
            "Date,Description,Amount,Currency,Paid By,Split Type,Participants,Split Values,Notes\n"
            "2026-06-14,Lunch,120.00,INR,Priya,equal,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)

        self.assertEqual(rows_imported, 1)
        self.assertEqual(status_str, 'PENDING')
        self.assertEqual(self.batch.status, 'PENDING')
        self.assertEqual(self.batch.total_rows, 1)
        self.assertEqual(ImportAnomaly.objects.filter(batch=self.batch).count(), 0)

    def test_header_validation_success_aliases_normalization(self):
        # Using mixed casing, whitespace, and aliases (e.g. expense_date, title, payer, split_between)
        csv_data = (
            "  Expense_Date  , Title ,  Value  , Currency , Payer , Split_Strategy , Split_Between , Split_Values , Notes \n"
            "2026-06-14,Lunch,120.00,INR,Priya,equal,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)

        self.assertEqual(rows_imported, 1)
        self.assertEqual(status_str, 'PENDING')
        self.assertEqual(self.batch.total_rows, 1)

    def test_header_validation_missing_date_rejected(self):
        csv_data = (
            "Description,Amount,Currency,Paid By,Split Type,Participants,Split Values,Notes\n"
            "Lunch,120.00,INR,Priya,equal,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)

        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertEqual(self.batch.status, 'REVIEW_REQUIRED')
        self.assertEqual(self.batch.total_rows, 0)

        # Verify Anomaly
        anomalies = ImportAnomaly.objects.filter(batch=self.batch)
        self.assertEqual(anomalies.count(), 1)
        anomaly = anomalies.first()
        self.assertEqual(anomaly.anomaly_type, 'MISSING_HEADERS')
        self.assertEqual(anomaly.severity, 'ERROR')
        self.assertIn('date', anomaly.description)
        self.assertIsNone(anomaly.row)

    def test_header_validation_missing_amount_rejected(self):
        csv_data = (
            "Date,Description,Currency,Paid By,Split Type,Participants,Split Values,Notes\n"
            "2026-06-14,Lunch,INR,Priya,equal,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertIn('amount', ImportAnomaly.objects.first().description)

    def test_header_validation_missing_currency_rejected(self):
        csv_data = (
            "Date,Description,Amount,Paid By,Split Type,Participants,Split Values,Notes\n"
            "2026-06-14,Lunch,10.00,Priya,equal,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertIn('currency', ImportAnomaly.objects.first().description)

    def test_header_validation_missing_participants_rejected(self):
        csv_data = (
            "Date,Description,Amount,Currency,Paid By,Split Type,Split Values,Notes\n"
            "2026-06-14,Lunch,10.00,INR,Priya,equal,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertIn('participants', ImportAnomaly.objects.first().description)

    def test_header_validation_missing_split_type_rejected(self):
        csv_data = (
            "Date,Description,Amount,Currency,Paid By,Participants,Split Values,Notes\n"
            "2026-06-14,Lunch,10.00,INR,Priya,Priya;Rohan,1;1,Memo note\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertIn('split_type', ImportAnomaly.objects.first().description)

    # --- CSV Parsing Tests ---

    def test_csv_parsing_correct_data_storage(self):
        csv_data = (
            "Date,Description,Amount,Currency,Paid By,Split Type,Participants,Split Values,Notes\n"
            "2026-06-14,Breakfast,80.00,INR,Rohan,equal,Rohan;Priya,1;1,Morning meal\n"
            "2026-06-15,Taxi,200.00,INR,Priya,exact,Rohan;Priya,120;80,Cab home\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)

        self.assertEqual(rows_imported, 2)
        self.assertEqual(self.batch.total_rows, 2)

        # Check rows
        rows = ImportRow.objects.filter(batch=self.batch).order_by('row_number')
        self.assertEqual(rows.count(), 2)

        row_1 = rows[0]
        self.assertEqual(row_1.row_number, 1)
        self.assertEqual(row_1.raw_data['Description'], 'Breakfast')
        self.assertEqual(row_1.raw_data['Amount'], '80.00')
        self.assertEqual(row_1.processing_notes, ["CSV parsed successfully"])

        row_2 = rows[1]
        self.assertEqual(row_2.row_number, 2)
        self.assertEqual(row_2.raw_data['Description'], 'Taxi')
        self.assertEqual(row_2.raw_data['Amount'], '200.00')
        self.assertEqual(row_2.processing_notes, ["CSV parsed successfully"])

    # --- Edge Cases ---

    def test_empty_csv(self):
        csv_data = ""
        file_obj = SimpleUploadedFile("empty.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 0)
        self.assertEqual(status_str, 'REVIEW_REQUIRED')
        self.assertEqual(ImportAnomaly.objects.filter(batch=self.batch).count(), 1)

    def test_malformed_rows_or_extra_columns(self):
        # Missing header in CSV schema, but CSV parses fine (DictReader allows extra columns)
        csv_data = (
            "Date,Description,Amount,Currency,Paid By,Split Type,Participants,Split Values,Notes,ExtraColumn\n"
            "2026-06-14,Lunch,120.00,INR,Priya,equal,Priya;Rohan,1;1,Memo note,Extra value\n"
        )
        file_obj = SimpleUploadedFile("test.csv", csv_data.encode('utf-8'))
        rows_imported, status_str = CSVImportService.parse_csv(self.batch, file_obj)
        self.assertEqual(rows_imported, 1)
        self.assertEqual(status_str, 'PENDING')
        row = ImportRow.objects.get(batch=self.batch)
        self.assertEqual(row.raw_data['ExtraColumn'], 'Extra value')


class CSVUploadAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='api_user', email='api@gmail.com', password='Password123'
        )
        self.non_member = User.objects.create_user(
            username='non_member', email='non_member@gmail.com', password='Password123'
        )
        self.group = Group.objects.create(
            name='API Group', base_currency='INR', created_by=self.user
        )
        # Active membership for self.user
        Membership.objects.create(
            group=self.group, user=self.user, role='OWNER', joined_at=timezone.now() - timedelta(days=5)
        )

        self.upload_url = reverse('import-upload')

        # Dummy CSV content
        self.valid_csv = (
            "Date,Description,Amount,Currency,Paid By,Split Type,Participants,Split Values,Notes\n"
            "2026-06-14,Coffee,50.00,INR,api_user,equal,api_user,1,Break\n"
        ).encode('utf-8')

    def test_upload_success_authenticated_member(self):
        self.client.force_authenticate(user=self.user)
        csv_file = SimpleUploadedFile("valid.csv", self.valid_csv, content_type="text/csv")
        payload = {
            'group_id': str(self.group.id),
            'file': csv_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('batch_id', response.data)
        self.assertEqual(response.data['rows_imported'], 1)
        self.assertEqual(response.data['status'], 'PENDING')

        # Check DB
        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(ImportRow.objects.count(), 1)

    def test_upload_rejection_unauthenticated(self):
        csv_file = SimpleUploadedFile("valid.csv", self.valid_csv, content_type="text/csv")
        payload = {
            'group_id': str(self.group.id),
            'file': csv_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_rejection_non_member(self):
        self.client.force_authenticate(user=self.non_member)
        csv_file = SimpleUploadedFile("valid.csv", self.valid_csv, content_type="text/csv")
        payload = {
            'group_id': str(self.group.id),
            'file': csv_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_rejection_empty_file(self):
        self.client.force_authenticate(user=self.user)
        empty_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        payload = {
            'group_id': str(self.group.id),
            'file': empty_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)

    def test_upload_rejection_invalid_extension(self):
        self.client.force_authenticate(user=self.user)
        text_file = SimpleUploadedFile("invalid.txt", b"some content", content_type="text/plain")
        payload = {
            'group_id': str(self.group.id),
            'file': text_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)

    def test_upload_rejection_invalid_group_id(self):
        self.client.force_authenticate(user=self.user)
        csv_file = SimpleUploadedFile("valid.csv", self.valid_csv, content_type="text/csv")
        payload = {
            'group_id': '00000000-0000-0000-0000-000000000000',
            'file': csv_file
        }
        response = self.client.post(self.upload_url, payload, format='multipart')
        # Returns 400 Bad Request because serializer group validation fails
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

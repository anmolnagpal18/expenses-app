from django.test import TestCase
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from expenses.models import StaticExchangeRate
from expenses.services import ExchangeRateService

class StaticExchangeRateTests(TestCase):
    def test_valid_exchange_rate_creation(self):
        rate = StaticExchangeRate.objects.create(
            from_currency='USD',
            to_currency='INR',
            rate=83.5000
        )
        self.assertIsNotNone(rate.id)
        self.assertEqual(rate.rate, 83.5000)

    def test_duplicate_currency_pair_rejected(self):
        from django.db import transaction
        StaticExchangeRate.objects.create(
            from_currency='EUR',
            to_currency='INR',
            rate=90.0000
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StaticExchangeRate.objects.create(
                    from_currency='EUR',
                    to_currency='INR',
                    rate=92.5000
                )

    def test_conversion_lookup_works(self):
        amt, rate = ExchangeRateService.convert_currency(100.00, 'INR', 'INR')
        self.assertEqual(amt, 100.00)
        self.assertEqual(rate, 1.0)

        with self.assertRaises(ValidationError):
            ExchangeRateService.convert_currency(10.00, 'USD', 'INR')

        StaticExchangeRate.objects.create(
            from_currency='USD',
            to_currency='INR',
            rate=80.0000
        )

        amt, rate = ExchangeRateService.convert_currency(5.00, 'USD', 'INR')
        self.assertEqual(amt, 400.00)
        self.assertEqual(rate, 80.0000)

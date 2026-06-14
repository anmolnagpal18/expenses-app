from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from expenses.split_strategies import (
    EqualSplitStrategy,
    PercentageSplitStrategy,
    ExactSplitStrategy,
    SharesSplitStrategy
)

class SplitStrategiesTests(TestCase):
    # --- EqualSplitStrategy ---

    def test_equal_split_even_division(self):
        strategy = EqualSplitStrategy()
        results = strategy.calculate_splits(Decimal('90.00'), ['u1', 'u2', 'u3'])
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r['amount_owed'], Decimal('30.00'))
            self.assertEqual(r['share_value'], Decimal('1.00'))

    def test_equal_split_remainder_distribution(self):
        strategy = EqualSplitStrategy()
        # 100 / 3 = 33.33 with 0.01 remainder. Remainder should go to the first participant (u1).
        results = strategy.calculate_splits(Decimal('100.00'), ['u1', 'u2', 'u3'])
        self.assertEqual(results[0]['user_id'], 'u1')
        self.assertEqual(results[0]['amount_owed'], Decimal('33.34'))
        self.assertEqual(results[1]['amount_owed'], Decimal('33.33'))
        self.assertEqual(results[2]['amount_owed'], Decimal('33.33'))
        self.assertEqual(sum(r['amount_owed'] for r in results), Decimal('100.00'))

    def test_equal_split_single_participant(self):
        strategy = EqualSplitStrategy()
        results = strategy.calculate_splits(Decimal('100.00'), ['u1'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['amount_owed'], Decimal('100.00'))

    def test_equal_split_zero_participants_rejected(self):
        strategy = EqualSplitStrategy()
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('100.00'), [])

    def test_equal_split_zero_or_negative_amount_rejected(self):
        strategy = EqualSplitStrategy()
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('0.00'), ['u1'])
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('-10.00'), ['u1'])

    # --- PercentageSplitStrategy ---

    def test_percentage_split_valid(self):
        strategy = PercentageSplitStrategy()
        payload = {'u1': Decimal('50.00'), 'u2': Decimal('30.00'), 'u3': Decimal('20.00')}
        results = strategy.calculate_splits(Decimal('100.00'), payload)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['amount_owed'], Decimal('50.00'))
        self.assertEqual(results[1]['amount_owed'], Decimal('30.00'))
        self.assertEqual(results[2]['amount_owed'], Decimal('20.00'))

    def test_percentage_split_not_totaling_100_rejected(self):
        strategy = PercentageSplitStrategy()
        payload = {'u1': Decimal('50.00'), 'u2': Decimal('40.00')}
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('100.00'), payload)

    def test_percentage_split_decimal_and_rounding(self):
        strategy = PercentageSplitStrategy()
        # 100 / 3 percent split (33.33%, 33.33%, 33.34%)
        payload = {'u1': Decimal('33.33'), 'u2': Decimal('33.33'), 'u3': Decimal('33.34')}
        results = strategy.calculate_splits(Decimal('100.00'), payload)
        self.assertEqual(sum(r['amount_owed'] for r in results), Decimal('100.00'))

    # --- ExactSplitStrategy ---

    def test_exact_split_valid(self):
        strategy = ExactSplitStrategy()
        payload = {'u1': Decimal('50.50'), 'u2': Decimal('49.50')}
        results = strategy.calculate_splits(Decimal('100.00'), payload)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['amount_owed'], Decimal('50.50'))
        self.assertEqual(results[1]['amount_owed'], Decimal('49.50'))

    def test_exact_split_mismatch_rejected(self):
        strategy = ExactSplitStrategy()
        payload = {'u1': Decimal('50.00'), 'u2': Decimal('40.00')}
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('100.00'), payload)

    # --- SharesSplitStrategy ---

    def test_shares_split_proportional(self):
        strategy = SharesSplitStrategy()
        payload = {'u1': Decimal('1'), 'u2': Decimal('2'), 'u3': Decimal('1')}
        results = strategy.calculate_splits(Decimal('100.00'), payload)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['amount_owed'], Decimal('25.00'))
        self.assertEqual(results[1]['amount_owed'], Decimal('50.00'))
        self.assertEqual(results[2]['amount_owed'], Decimal('25.00'))

    def test_shares_split_invalid_shares_rejected(self):
        strategy = SharesSplitStrategy()
        # Zero total shares
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('100.00'), {'u1': Decimal('0'), 'u2': Decimal('0')})
        # Negative shares
        with self.assertRaises(ValidationError):
            strategy.calculate_splits(Decimal('100.00'), {'u1': Decimal('2'), 'u2': Decimal('-1')})

    def test_shares_split_rounding_correction(self):
        strategy = SharesSplitStrategy()
        # 100 divided into 3 shares (1:1:1)
        payload = {'u1': Decimal('1'), 'u2': Decimal('1'), 'u3': Decimal('1')}
        results = strategy.calculate_splits(Decimal('100.00'), payload)
        self.assertEqual(sum(r['amount_owed'] for r in results), Decimal('100.00'))
        self.assertEqual(results[0]['amount_owed'], Decimal('33.34'))

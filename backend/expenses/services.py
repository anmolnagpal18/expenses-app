from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Expense, Settlement, StaticExchangeRate
from .repositories import ExpenseRepository, SettlementRepository, ExchangeRateRepository

class ExchangeRateService:
    @staticmethod
    def convert_currency(amount, from_currency, to_currency):
        """
        Converts amount from from_currency to to_currency using static rates.
        Returns a tuple: (converted_amount, exchange_rate)
        """
        if from_currency == to_currency:
            return amount, 1.0
            
        rate = ExchangeRateRepository.get_rate(from_currency, to_currency)
        if rate is None:
            raise ValidationError(f"No exchange rate found from {from_currency} to {to_currency}.")
            
        converted = round(amount * rate, 2)
        return converted, rate

class ExpenseService:
    @staticmethod
    @transaction.atomic
    def create_expense(group_id, description, date, original_amount, currency, split_type, created_by, source="MANUAL"):
        """
        Skeleton: To be fully implemented in a future commit.
        """
        # Minimal placeholder
        pass

    @staticmethod
    @transaction.atomic
    def update_expense(expense_id, description=None, date=None, original_amount=None, currency=None, split_type=None):
        """
        Skeleton: To be fully implemented in a future commit.
        """
        # Minimal placeholder
        pass

    @staticmethod
    @transaction.atomic
    def delete_expense(expense_id):
        """
        Performs a soft delete on an expense by setting is_deleted=True and deleted_at=now.
        """
        expense = ExpenseRepository.get_by_id(expense_id)
        if not expense:
            raise ValidationError("Expense does not exist.")
        expense.is_deleted = True
        expense.deleted_at = timezone.now()
        expense.save()
        return expense

class SettlementService:
    @staticmethod
    @transaction.atomic
    def create_settlement(group_id, from_user_id, to_user_id, original_amount, currency, settlement_date, source="MANUAL"):
        """
        Skeleton: To be fully implemented in a future commit.
        """
        # Minimal placeholder
        pass

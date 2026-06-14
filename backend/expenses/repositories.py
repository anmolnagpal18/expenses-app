from .models import Expense, Settlement, StaticExchangeRate, BalanceSnapshot

class ExpenseRepository:
    @staticmethod
    def get_by_id(expense_id):
        try:
            return Expense.objects.get(pk=expense_id)
        except Expense.DoesNotExist:
            return None

    @staticmethod
    def get_group_expenses(group_id, include_deleted=False):
        qs = Expense.objects.filter(group_id=group_id)
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs

class SettlementRepository:
    @staticmethod
    def get_by_id(settlement_id):
        try:
            return Settlement.objects.get(pk=settlement_id)
        except Settlement.DoesNotExist:
            return None

    @staticmethod
    def get_group_settlements(group_id, include_deleted=False):
        qs = Settlement.objects.filter(group_id=group_id)
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        return qs

class ExchangeRateRepository:
    @staticmethod
    def get_by_id(rate_id):
        try:
            return StaticExchangeRate.objects.get(pk=rate_id)
        except StaticExchangeRate.DoesNotExist:
            return None

    @staticmethod
    def get_rate(from_currency, to_currency):
        # Exact match
        rate_obj = StaticExchangeRate.objects.filter(
            from_currency=from_currency,
            to_currency=to_currency
        ).first()
        if rate_obj:
            return rate_obj.rate
        return None

class BalanceSnapshotRepository:
    @staticmethod
    def get_by_id(snapshot_id):
        try:
            return BalanceSnapshot.objects.get(pk=snapshot_id)
        except BalanceSnapshot.DoesNotExist:
            return None

    @staticmethod
    def get_group_snapshots(group_id):
        return BalanceSnapshot.objects.filter(group_id=group_id)

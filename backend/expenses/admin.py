from django.contrib import admin
from .models import (
    StaticExchangeRate,
    Expense,
    ExpenseContribution,
    ExpenseSplit,
    Settlement,
    BalanceSnapshot
)

@admin.register(StaticExchangeRate)
class StaticExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('from_currency', 'to_currency', 'rate', 'created_at')
    search_fields = ('from_currency', 'to_currency')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'group', 'original_amount', 'currency', 'split_type', 'date', 'is_deleted')
    list_filter = ('group', 'split_type', 'is_deleted')
    search_fields = ('description',)

@admin.register(ExpenseContribution)
class ExpenseContributionAdmin(admin.ModelAdmin):
    list_display = ('expense', 'user', 'amount_paid')
    list_filter = ('user',)

@admin.register(ExpenseSplit)
class ExpenseSplitAdmin(admin.ModelAdmin):
    list_display = ('expense', 'user', 'share_value', 'amount_owed')
    list_filter = ('user',)

@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ('group', 'from_user', 'to_user', 'original_amount', 'currency', 'settlement_date', 'is_deleted')
    list_filter = ('group', 'is_deleted')

@admin.register(BalanceSnapshot)
class BalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ('group', 'from_user', 'to_user', 'balance', 'updated_at')
    list_filter = ('group',)

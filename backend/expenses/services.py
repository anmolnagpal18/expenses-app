from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from .models import Expense, Settlement, StaticExchangeRate
from .repositories import ExpenseRepository, SettlementRepository, ExchangeRateRepository

class ExchangeRateService:
    @staticmethod
    def convert_currency(amount, from_currency, to_currency):
        """
        Converts amount from from_currency to to_currency using static rates.
        Returns a tuple: (converted_amount, exchange_rate)
        """
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if from_currency == to_currency:
            return amount, Decimal('1.0')
            
        rate = ExchangeRateRepository.get_rate(from_currency, to_currency)
        if rate is None:
            raise ValidationError(f"No exchange rate found from {from_currency} to {to_currency}.")
            
        converted = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return converted, rate

class ExpenseService:
    @staticmethod
    @transaction.atomic
    def create_expense(group_id, description, date, original_amount, currency, split_type, created_by, contributors, splits, source="MANUAL"):
        """
        Creates an expense record, validating dynamic memberships and executing the split strategy.
        """
        from groups.repositories import GroupRepository
        from groups.services import MembershipValidationService
        from .split_strategies import STRATEGY_REGISTRY
        from datetime import datetime, time
        from django.contrib.auth import get_user_model
        
        group = GroupRepository.get_by_id(group_id)
        if not group:
            raise ValidationError("Group does not exist.")

        # Convert date to timezone-aware datetime at start of day for membership checks
        transaction_dt = timezone.make_aware(datetime.combine(date, time.min))

        # 1. Validate active memberships for expense date
        User = get_user_model()
        if created_by:
            MembershipValidationService.validate_active_membership(group_id, created_by.id, transaction_dt)

        for c in contributors:
            MembershipValidationService.validate_active_membership(group_id, c['user_id'], transaction_dt)

        strategy = STRATEGY_REGISTRY.get(split_type)
        if not strategy:
            raise ValidationError(f"Unsupported split type: {split_type}")

        # Parse splits based on format expected by strategy registry
        if split_type == 'equal':
            if isinstance(splits, list):
                if splits and isinstance(splits[0], dict):
                    participants_data = [s['user_id'] for s in splits]
                else:
                    participants_data = splits
            elif isinstance(splits, dict):
                participants_data = list(splits.keys())
            else:
                raise ValidationError("Invalid splits format for equal split.")
        else:
            if isinstance(splits, list):
                participants_data = {s['user_id']: s['share_value'] for s in splits}
            elif isinstance(splits, dict):
                participants_data = splits
            else:
                raise ValidationError("Invalid splits format.")

        for user_id in participants_data:
            MembershipValidationService.validate_active_membership(group_id, user_id, transaction_dt)

        # 2. Check sum of contributions equals original_amount
        original_decimal = Decimal(str(original_amount))
        total_paid = sum(Decimal(str(c['amount_paid'])) for c in contributors)
        if total_paid != original_decimal:
            raise ValidationError(f"Total contributions ({total_paid}) must equal original_amount ({original_decimal}).")

        # 3. Resolve exchange rate and converted amount
        converted_amount, exchange_rate = ExchangeRateService.convert_currency(original_decimal, currency, group.base_currency)

        # 4. Execute split strategy
        split_results = strategy.calculate_splits(original_decimal, participants_data)

        # 5. Create Expense record
        expense = Expense.objects.create(
            group=group,
            description=description,
            date=date,
            original_amount=original_decimal,
            converted_amount=converted_amount,
            currency=currency,
            exchange_rate=exchange_rate,
            split_type=split_type,
            created_by=created_by,
            source=source
        )

        # 6. Create ExpenseContribution records
        for c in contributors:
            user = User.objects.get(pk=c['user_id'])
            ExpenseRepository.create_contribution(
                expense=expense,
                user=user,
                amount_paid=Decimal(str(c['amount_paid']))
            )

        # 7. Create ExpenseSplit records
        for res in split_results:
            user = User.objects.get(pk=res['user_id'])
            amount_owed_base = (res['amount_owed'] * exchange_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            ExpenseRepository.create_split(
                expense=expense,
                user=user,
                share_value=res['share_value'],
                amount_owed=amount_owed_base
            )

        # Refresh the balance snapshot for the group
        BalanceSnapshotService.refresh_group_snapshot(group_id)

        return expense

    @staticmethod
    @transaction.atomic
    def update_expense(expense_id, description=None, date=None, original_amount=None, currency=None, split_type=None):
        """
        Skeleton: To be fully implemented in a future commit.
        """
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
        
        # Refresh the balance snapshot for the group
        BalanceSnapshotService.refresh_group_snapshot(expense.group_id)
        return expense

class SettlementService:
    @staticmethod
    @transaction.atomic
    def create_settlement(group_id, from_user_id, to_user_id, original_amount, currency, settlement_date, source="MANUAL"):
        from groups.repositories import GroupRepository
        from django.contrib.auth import get_user_model
        
        group = GroupRepository.get_by_id(group_id)
        if not group:
            raise ValidationError("Group does not exist.")
            
        User = get_user_model()
        try:
            from_user = User.objects.get(pk=from_user_id)
        except User.DoesNotExist:
            raise ValidationError("Payer does not exist.")
            
        try:
            to_user = User.objects.get(pk=to_user_id)
        except User.DoesNotExist:
            raise ValidationError("Payee does not exist.")
            
        # Service-layer validation: check both users belong to the group
        from groups.repositories import MembershipRepository
        from_memberships = MembershipRepository.get_user_membership_in_group(group.id, from_user.id)
        to_memberships = MembershipRepository.get_user_membership_in_group(group.id, to_user.id)
        if not from_memberships.exists():
            raise ValidationError(f"Payer ({from_user.email}) must be a member of the group (historical or active).")
        if not to_memberships.exists():
            raise ValidationError(f"Payee ({to_user.email}) must be a member of the group (historical or active).")
            
        original_decimal = Decimal(str(original_amount))
        
        # 1. Resolve exchange rate and converted amount
        converted_amount, exchange_rate = ExchangeRateService.convert_currency(original_decimal, currency, group.base_currency)
        
        # 2. Create the settlement (Django will run Settlement.clean() in its save() override)
        settlement = Settlement.objects.create(
            group=group,
            from_user=from_user,
            to_user=to_user,
            original_amount=original_decimal,
            converted_amount=converted_amount,
            currency=currency,
            exchange_rate=exchange_rate,
            settlement_date=settlement_date,
            source=source
        )
        
        # 3. Refresh balance snapshot
        BalanceSnapshotService.refresh_group_snapshot(group_id)
        
        return settlement

class BalanceSnapshotService:
    @staticmethod
    @transaction.atomic
    def refresh_group_snapshot(group_id):
        """
        Recalculates bilateral balances and updates BalanceSnapshot table for a group.
        """
        from groups.models import Group
        from django.contrib.auth import get_user_model
        from .models import BalanceSnapshot
        from .repositories import BalanceSnapshotRepository
        from .balance_engine import BalanceEngine

        User = get_user_model()
        group = Group.objects.get(pk=group_id)

        # 1. Compute direct bilateral balances
        result = BalanceEngine.calculate_group_balances(group_id)
        balances = result["balances"]

        # 2. Clear existing group snapshot entries
        BalanceSnapshotRepository.delete_group_snapshots(group_id)

        # 3. Bulk create refreshed snapshots
        snapshots = []
        for bal in balances:
            from_user = User.objects.get(pk=bal["from_user_id"])
            to_user = User.objects.get(pk=bal["to_user_id"])
            snapshots.append(
                BalanceSnapshot(
                    group=group,
                    from_user=from_user,
                    to_user=to_user,
                    balance=bal["amount"],
                    calculation_version=1
                )
            )

        if snapshots:
            BalanceSnapshotRepository.bulk_create_snapshots(snapshots)

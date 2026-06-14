from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from django.core.exceptions import ValidationError

class BaseSplitStrategy(ABC):
    @abstractmethod
    def calculate_splits(self, total_amount, participants_data):
        """
        Calculates split amounts for each user.
        participants_data can be a list of user IDs (for Equal split) or
        a dict mapping user ID -> split configuration value (for other splits).
        Returns a list of dicts: [{'user_id': ..., 'share_value': ..., 'amount_owed': ...}]
        """
        pass

class EqualSplitStrategy(BaseSplitStrategy):
    def calculate_splits(self, total_amount, participants_data):
        # participants_data is a list of user IDs
        if not participants_data:
            raise ValidationError("Equal split requires at least one participant.")
        
        total_decimal = Decimal(str(total_amount))
        if total_decimal <= 0:
            raise ValidationError("Expense amount must be greater than zero.")

        n = len(participants_data)
        base_share = (total_decimal / n).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        remainder = total_decimal - (base_share * n)
        
        results = []
        for i, user_id in enumerate(participants_data):
            owed = base_share
            if i == 0:
                owed += remainder
            results.append({
                "user_id": user_id,
                "share_value": Decimal('1.00'),
                "amount_owed": owed
            })
        return results

class PercentageSplitStrategy(BaseSplitStrategy):
    def calculate_splits(self, total_amount, participants_data):
        # participants_data is a dict of user_id -> percentage
        if not participants_data:
            raise ValidationError("Percentage split requires at least one participant.")
        
        total_decimal = Decimal(str(total_amount))
        total_pct = sum(Decimal(str(val)) for val in participants_data.values())
        if total_pct != Decimal('100.00') and total_pct != Decimal('100'):
            raise ValidationError(f"Percentages must sum to exactly 100 (got {total_pct}).")

        results = []
        sum_owed = Decimal('0.00')
        sorted_users = list(participants_data.keys())
        
        amounts = {}
        for user_id in sorted_users:
            pct = Decimal(str(participants_data[user_id]))
            owed = (total_decimal * (pct / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            amounts[user_id] = owed
            sum_owed += owed

        remainder = total_decimal - sum_owed
        if sorted_users:
            amounts[sorted_users[0]] += remainder

        for user_id in sorted_users:
            results.append({
                "user_id": user_id,
                "share_value": Decimal(str(participants_data[user_id])),
                "amount_owed": amounts[user_id]
            })
        return results

class ExactSplitStrategy(BaseSplitStrategy):
    def calculate_splits(self, total_amount, participants_data):
        # participants_data is a dict of user_id -> exact amount
        if not participants_data:
            raise ValidationError("Exact split requires at least one participant.")
        
        total_decimal = Decimal(str(total_amount))
        total_exact = sum(Decimal(str(val)) for val in participants_data.values())
        if total_exact != total_decimal:
            raise ValidationError(f"Exact split amounts must sum to the expense total of {total_amount} (got {total_exact}).")

        results = []
        for user_id, amt in participants_data.items():
            results.append({
                "user_id": user_id,
                "share_value": Decimal(str(amt)),
                "amount_owed": Decimal(str(amt))
            })
        return results

class SharesSplitStrategy(BaseSplitStrategy):
    def calculate_splits(self, total_amount, participants_data):
        # participants_data is a dict of user_id -> share value
        if not participants_data:
            raise ValidationError("Shares split requires at least one participant.")
            
        total_decimal = Decimal(str(total_amount))
        total_shares = sum(Decimal(str(val)) for val in participants_data.values())
        if total_shares <= 0:
            raise ValidationError("Total shares must be strictly positive.")
            
        for user_id, sh in participants_data.items():
            if Decimal(str(sh)) <= 0:
                raise ValidationError("Individual shares must be strictly positive.")

        results = []
        sum_owed = Decimal('0.00')
        sorted_users = list(participants_data.keys())
        
        amounts = {}
        for user_id in sorted_users:
            sh = Decimal(str(participants_data[user_id]))
            owed = (total_decimal * (sh / total_shares)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            amounts[user_id] = owed
            sum_owed += owed
            
        remainder = total_decimal - sum_owed
        if sorted_users:
            amounts[sorted_users[0]] += remainder

        for user_id in sorted_users:
            results.append({
                "user_id": user_id,
                "share_value": Decimal(str(participants_data[user_id])),
                "amount_owed": amounts[user_id]
            })
        return results

STRATEGY_REGISTRY = {
    "equal": EqualSplitStrategy(),
    "percentage": PercentageSplitStrategy(),
    "exact": ExactSplitStrategy(),
    "shares": SharesSplitStrategy(),
}

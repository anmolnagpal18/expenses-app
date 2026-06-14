from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from groups.serializers import GroupSerializer, SUPPORTED_CURRENCIES
from users.serializers import UserSerializer
from .models import Expense, ExpenseContribution, ExpenseSplit

User = get_user_model()

class ExpenseContributionInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_user_id(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

    def validate_amount_paid(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount paid must be greater than zero.")
        return value

class ExpenseSplitInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    split_input_value = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    def validate_user_id(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

class CreateExpenseSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    description = serializers.CharField(max_length=255)
    date = serializers.DateField()
    original_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    split_type = serializers.ChoiceField(choices=Expense.SPLIT_CHOICES)
    contributors = ExpenseContributionInputSerializer(many=True)
    participants = ExpenseSplitInputSerializer(many=True)

    def validate_original_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Original amount must be greater than zero.")
        return value

    def validate_currency(self, value):
        currency_upper = value.upper().strip()
        if currency_upper not in SUPPORTED_CURRENCIES:
            raise serializers.ValidationError(
                f"Currency '{value}' is not supported. Supported currencies are: {', '.join(SUPPORTED_CURRENCIES)}"
            )
        return currency_upper

    def validate_contributors(self, value):
        if not value:
            raise serializers.ValidationError("Contributors list is required and cannot be empty.")
        return value

    def validate_participants(self, value):
        if not value:
            raise serializers.ValidationError("Participants list is required and cannot be empty.")
        return value

    def validate_group_id(self, value):
        from groups.models import Group
        if not Group.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Group does not exist.")
        return value


class ExpenseContributionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseContribution
        fields = ('id', 'user', 'amount_paid')


class ExpenseSplitSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ('id', 'user', 'share_value', 'amount_owed')


class ExpenseSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)
    contributions = ExpenseContributionSerializer(many=True, read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = (
            'id',
            'group',
            'description',
            'date',
            'original_amount',
            'converted_amount',
            'currency',
            'exchange_rate',
            'split_type',
            'created_by',
            'source',
            'is_deleted',
            'deleted_at',
            'created_at',
            'contributions',
            'splits'
        )

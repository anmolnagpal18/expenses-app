from rest_framework import serializers
from django.contrib.auth import get_user_model
from groups.serializers import GroupSerializer, SUPPORTED_CURRENCIES
from users.serializers import UserSerializer
from groups.repositories import MembershipRepository
from .models import Settlement
from decimal import Decimal

User = get_user_model()

class CreateSettlementSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    from_user_id = serializers.IntegerField()
    to_user_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    settlement_date = serializers.DateField()

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_currency(self, value):
        currency_upper = value.upper().strip()
        if currency_upper not in SUPPORTED_CURRENCIES:
            raise serializers.ValidationError(
                f"Currency '{value}' is not supported. Supported currencies are: {', '.join(SUPPORTED_CURRENCIES)}"
            )
        return currency_upper

    def validate_group_id(self, value):
        from groups.models import Group
        if not Group.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Group does not exist.")
        return value

    def validate(self, data):
        group_id = data.get('group_id')
        from_user_id = data.get('from_user_id')
        to_user_id = data.get('to_user_id')

        if from_user_id == to_user_id:
            raise serializers.ValidationError("Payer and payee must be distinct users.")

        try:
            from_user = User.objects.get(pk=from_user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({"from_user_id": "Payer user does not exist."})

        try:
            to_user = User.objects.get(pk=to_user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError({"to_user_id": "Payee user does not exist."})

        # Check membership validation: both users belong to the group (historical membership allowed)
        from_memberships = MembershipRepository.get_user_membership_in_group(group_id, from_user_id)
        to_memberships = MembershipRepository.get_user_membership_in_group(group_id, to_user_id)

        if not from_memberships.exists():
            raise serializers.ValidationError(
                {"from_user_id": f"Payer ({from_user.email}) must be a member of the group (historical or active)."}
            )
        if not to_memberships.exists():
            raise serializers.ValidationError(
                {"to_user_id": f"Payee ({to_user.email}) must be a member of the group (historical or active)."}
            )

        return data


class SettlementSerializer(serializers.ModelSerializer):
    payer = UserSerializer(source='from_user', read_only=True)
    receiver = UserSerializer(source='to_user', read_only=True)
    group = GroupSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = (
            'id',
            'group',
            'payer',
            'receiver',
            'original_amount',
            'converted_amount',
            'currency',
            'exchange_rate',
            'settlement_date',
            'source',
            'is_deleted',
            'deleted_at',
            'created_at'
        )

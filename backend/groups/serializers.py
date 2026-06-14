from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Group, Membership
from users.serializers import UserSerializer

User = get_user_model()

SUPPORTED_CURRENCIES = ('INR', 'USD', 'EUR', 'GBP')

class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    membership_duration = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ('id', 'user', 'role', 'joined_at', 'left_at', 'is_active', 'membership_duration')
        read_only_fields = ('id', 'user', 'is_active', 'membership_duration')

    def get_membership_duration(self, obj):
        end = obj.left_at or timezone.now()
        return (end - obj.joined_at).days

class GroupSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = Group
        fields = ('id', 'name', 'base_currency', 'created_by', 'created_at', 'memberships')
        read_only_fields = ('id', 'created_by', 'created_at', 'memberships')

class CreateGroupSerializer(serializers.ModelSerializer):
    base_currency = serializers.ChoiceField(choices=SUPPORTED_CURRENCIES, default='INR')

    class Meta:
        model = Group
        fields = ('id', 'name', 'base_currency')
        read_only_fields = ('id',)

class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.ROLE_CHOICES, default='MEMBER')
    joined_at = serializers.DateTimeField(required=False, allow_null=True)
    left_at = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        email = value.lower().strip()
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError("No user found with this email address.")
        return email

    def validate(self, data):
        # Standardize joined_at if not provided
        if not data.get('joined_at'):
            data['joined_at'] = timezone.now()
        
        left_at = data.get('left_at')
        joined_at = data['joined_at']
        if left_at and left_at <= joined_at:
            raise serializers.ValidationError({"left_at": "left_at must be strictly after joined_at."})

        # Early check for active memberships using context group_id
        email = data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                group_id = self.context.get('group_id')
                if group_id:
                    from .repositories import MembershipRepository
                    active_membership = MembershipRepository.get_active_membership_at(group_id, user.id, joined_at)
                    if active_membership:
                        raise serializers.ValidationError(
                            {"email": "This user already has an active membership in this group at the specified start time."}
                        )
            except User.DoesNotExist:
                pass

        return data

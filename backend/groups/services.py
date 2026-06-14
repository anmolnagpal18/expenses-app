from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Group, Membership
from .repositories import GroupRepository, MembershipRepository

class GroupService:
    @staticmethod
    @transaction.atomic
    def create_group(name, base_currency, creator_user):
        """
        Creates a new group and automatically registers the creator 
        as the initial OWNER membership.
        """
        group = Group.objects.create(
            name=name,
            base_currency=base_currency,
            created_by=creator_user
        )
        Membership.objects.create(
            group=group,
            user=creator_user,
            role='OWNER',
            joined_at=group.created_at or timezone.now()
        )
        return group

class MembershipService:
    @staticmethod
    def add_member(group_id, user_id, role, joined_at, left_at=None, membership_source='MANUAL'):
        """
        Registers a membership period for a user in a group.
        Performs timeline order and overlap checks.
        """
        group = GroupRepository.get_by_id(group_id)
        if not group:
            raise ValidationError("Group does not exist.")
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError("User does not exist.")

        membership = Membership(
            group=group,
            user=user,
            role=role,
            joined_at=joined_at,
            left_at=left_at
        )
        # This will call membership.clean() and validate overlapping, left_at, etc.
        membership.save()
        return membership

    @staticmethod
    def set_member_left_date(membership_id, left_at):
        """
        Caps a membership period by setting left_at, marking the user inactive
        for future expenses while retaining historical balance references.
        """
        membership = MembershipRepository.get_by_id(membership_id)
        if not membership:
            raise ValidationError("Membership does not exist.")
        membership.left_at = left_at
        membership.save()
        return membership

    @staticmethod
    def change_member_role(membership_id, new_role):
        """
        Modifies a user's role. Enforces ownership count validations.
        """
        membership = MembershipRepository.get_by_id(membership_id)
        if not membership:
            raise ValidationError("Membership does not exist.")
        membership.role = new_role
        membership.save()
        return membership

class MembershipValidationService:
    @staticmethod
    def validate_active_membership(group_id, user_id, transaction_date):
        """
        Verifies that a user has an active membership in the group on the transaction date/time.
        Raises ValidationError if not active.
        """
        membership = MembershipRepository.get_active_membership_at(group_id, user_id, transaction_date)
        if not membership:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id)
                email = user.email
            except User.DoesNotExist:
                email = f"User ID {user_id}"
            raise ValidationError(f"User {email} does not have an active membership in the group on {transaction_date.date()}.")
        return membership

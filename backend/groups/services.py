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
        # Skeleton: Implementation will be added in APIs commit
        pass

class MembershipService:
    @staticmethod
    def add_member(group_id, user_id, role, joined_at, left_at=None):
        """
        Registers a membership period for a user in a group.
        Performs timeline order and overlap checks.
        """
        # Skeleton: Implementation will be added in APIs commit
        pass

    @staticmethod
    def set_member_left_date(membership_id, left_at):
        """
        Caps a membership period by setting left_at, marking the user inactive
        for future expenses while retaining historical balance references.
        """
        # Skeleton: Implementation will be added in APIs commit
        pass

    @staticmethod
    def change_member_role(membership_id, new_role):
        """
        Modifies a user's role. Enforces ownership count validations.
        """
        # Skeleton: Implementation will be added in APIs commit
        pass

from rest_framework import permissions
from django.utils import timezone
from django.core.exceptions import ValidationError
from groups.repositories import MembershipRepository
from .models import Expense

class IsGroupMember(permissions.BasePermission):
    """
    Permission to allow access only to active members of the group.
    For detail views, it resolves the group from the Expense ID.
    For creation/listing views, it resolves the group from group_id in request payload.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        expense_id = view.kwargs.get('pk') or view.kwargs.get('id')
        if expense_id:
            try:
                expense = Expense.objects.only('group_id').get(pk=expense_id)
                group_id = expense.group_id
            except (Expense.DoesNotExist, ValueError, ValidationError):
                from .models import Settlement
                try:
                    settlement = Settlement.objects.only('group_id').get(pk=expense_id)
                    group_id = settlement.group_id
                except (Settlement.DoesNotExist, ValueError, ValidationError):
                    return False
        else:
            group_id = request.data.get('group_id')
            if not group_id:
                return False

        # If the group does not exist, let serializer/service handle the validation error (400 Bad Request)
        from groups.models import Group
        try:
            if not Group.objects.filter(pk=group_id).exists():
                return True
        except (ValueError, ValidationError):
            return True

        membership = MembershipRepository.get_active_membership_at(group_id, request.user.id, timezone.now())
        return membership is not None and membership.role in ('OWNER', 'ADMIN', 'MEMBER')

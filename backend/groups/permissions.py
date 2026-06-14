from django.utils import timezone
from rest_framework import permissions
from .repositories import MembershipRepository

def get_user_role_in_group(user, group_id):
    if not user or not user.is_authenticated or not group_id:
        return None
    # TODO: Cache membership lookup per request
    # Check if user has an active membership in the group at the current time
    membership = MembershipRepository.get_active_membership_at(group_id, user.id, timezone.now())
    return membership.role if membership else None

class IsGroupMember(permissions.BasePermission):
    """
    Allows access only to active members of the group.
    """
    def has_permission(self, request, view):
        group_id = view.kwargs.get('id') or view.kwargs.get('group_id')
        if not group_id:
            return False
        role = get_user_role_in_group(request.user, group_id)
        return role in ('OWNER', 'ADMIN', 'MEMBER')

class IsGroupAdminOrOwner(permissions.BasePermission):
    """
    Allows access only to group OWNERs or ADMINs.
    """
    def has_permission(self, request, view):
        group_id = view.kwargs.get('id') or view.kwargs.get('group_id')
        if not group_id:
            return False
        role = get_user_role_in_group(request.user, group_id)
        return role in ('OWNER', 'ADMIN')

class IsGroupOwner(permissions.BasePermission):
    """
    Allows access only to group OWNERs.
    """
    def has_permission(self, request, view):
        group_id = view.kwargs.get('id') or view.kwargs.get('group_id')
        if not group_id:
            return False
        role = get_user_role_in_group(request.user, group_id)
        return role == 'OWNER'

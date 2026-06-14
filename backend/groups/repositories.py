from django.utils import timezone
from .models import Group, Membership

class GroupRepository:
    @staticmethod
    def get_by_id(group_id):
        try:
            return Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            return None

    @staticmethod
    def get_user_groups(user):
        """
        Retrieves all groups that a user has ever joined (active or inactive).
        """
        return Group.objects.filter(memberships__user=user).distinct()

class MembershipRepository:
    @staticmethod
    def get_by_id(membership_id):
        try:
            return Membership.objects.get(pk=membership_id)
        except Membership.DoesNotExist:
            return None

    @staticmethod
    def get_group_memberships(group_id, active_only=False):
        """
        Retrieves memberships for a group.
        """
        qs = Membership.objects.filter(group_id=group_id)
        if active_only:
            now = timezone.now()
            # Active if joined_at <= now AND (left_at IS NULL OR left_at >= now)
            qs = qs.filter(
                joined_at__lte=now
            ).filter(
                models.Q(left_at__isnull=True) | models.Q(left_at__gte=now)
            )
        return qs

    @staticmethod
    def get_user_membership_in_group(group_id, user_id):
        """
        Retrieves all membership intervals for a user in a group.
        """
        return Membership.objects.filter(group_id=group_id, user_id=user_id)

    @staticmethod
    def get_active_membership_at(group_id, user_id, target_date):
        """
        Finds a membership covering a specific transaction datetime.
        """
        return Membership.objects.filter(
            group_id=group_id,
            user_id=user_id,
            joined_at__lte=target_date
        ).filter(
            models.Q(left_at__isnull=True) | models.Q(left_at__gte=target_date)
        ).first()

    @staticmethod
    def check_overlap(group_id, user_id, joined_at, left_at=None, exclude_id=None):
        """
        Returns true if there's any overlapping membership period.
        """
        qs = Membership.objects.filter(group_id=group_id, user_id=user_id)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)

        # self: [S1, E1]
        # other: [S2, E2]
        # Overlaps if: self_end >= other.joined_at AND other_end >= self.joined_at
        end_date = left_at if left_at else timezone.make_aware(timezone.datetime.max)
        
        for other in qs:
            other_end = other.left_at if other.left_at else timezone.make_aware(timezone.datetime.max)
            if not (end_date < other.joined_at or other_end < joined_at):
                return True
        return False

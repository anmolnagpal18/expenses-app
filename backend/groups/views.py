from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError

from .models import Group, Membership
from .repositories import GroupRepository
from .services import GroupService, MembershipService
from .serializers import (
    GroupSerializer, 
    MembershipSerializer, 
    CreateGroupSerializer, 
    AddMemberSerializer
)
from .permissions import IsGroupMember, IsGroupAdminOrOwner

class GroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Retrieve all groups that the user has ever joined
        groups = GroupRepository.get_user_groups(request.user).prefetch_related('memberships__user')
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateGroupSerializer(data=request.data)
        if serializer.is_valid():
            try:
                group = GroupService.create_group(
                    name=serializer.validated_data['name'],
                    base_currency=serializer.validated_data.get('base_currency', 'INR'),
                    creator_user=request.user
                )
                # Fetch again with prefetched relationships to avoid lazy loading in serializer
                group_fetched = Group.objects.prefetch_related('memberships__user').get(pk=group.id)
                output_serializer = GroupSerializer(group_fetched)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request, id):
        try:
            # Prefetch to prevent N+1 queries
            group = Group.objects.prefetch_related('memberships__user').get(pk=id)
        except Group.DoesNotExist:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = GroupSerializer(group)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AddMemberView(APIView):
    permission_classes = [IsAuthenticated, IsGroupAdminOrOwner]

    def post(self, request, id):
        serializer = AddMemberSerializer(data=request.data, context={'group_id': id})
        if serializer.is_valid():
            email = serializer.validated_data['email']
            role = serializer.validated_data['role']
            joined_at = serializer.validated_data['joined_at']
            left_at = serializer.validated_data.get('left_at')

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(email=email)

            try:
                membership = MembershipService.add_member(
                    group_id=id,
                    user_id=user.id,
                    role=role,
                    joined_at=joined_at,
                    left_at=left_at
                )
                return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MembershipDetailView(APIView):
    permission_classes = [IsAuthenticated, IsGroupAdminOrOwner]

    def put(self, request, group_id, membership_id):
        return Response(
            {"detail": "Placeholder: Membership updates (role change, timeline adjustment) will be implemented in a future commit."},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    def patch(self, request, group_id, membership_id):
        return Response(
            {"detail": "Placeholder: Membership updates (role change, timeline adjustment) will be implemented in a future commit."},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    def delete(self, request, group_id, membership_id):
        return Response(
            {"detail": "Placeholder: Membership deletion or leaving group will be implemented in a future commit."},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class GroupBalancesView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request, id):
        from expenses.balance_engine import BalanceEngine
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Calculate direct bilateral balances for group
        result = BalanceEngine.calculate_group_balances(id)
        balances = result.get("balances", [])

        # Fetch all user info to serialize them with username and email
        user_ids = set()
        for bal in balances:
            user_ids.add(bal["from_user_id"])
            user_ids.add(bal["to_user_id"])
        
        users_map = {
            user.id: {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            } for user in User.objects.filter(id__in=user_ids)
        }

        serialized_balances = []
        for bal in balances:
            from_user = users_map.get(bal["from_user_id"])
            to_user = users_map.get(bal["to_user_id"])
            serialized_balances.append({
                "from_user": from_user,
                "to_user": to_user,
                "amount": str(bal["amount"])
            })

        return Response(serialized_balances, status=status.HTTP_200_OK)


class GroupBalanceExplanationView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request, id):
        from expenses.balance_engine import BalanceEngine
        import uuid

        from_user_id_str = request.query_params.get('from_user_id')
        to_user_id_str = request.query_params.get('to_user_id')

        if not from_user_id_str or not to_user_id_str:
            return Response(
                {"detail": "from_user_id and to_user_id query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from_user_id = int(from_user_id_str)
            to_user_id = int(to_user_id_str)
        except ValueError:
            try:
                from_user_id = uuid.UUID(from_user_id_str)
                to_user_id = uuid.UUID(to_user_id_str)
            except ValueError:
                return Response(
                    {"detail": "Invalid user ID format."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        explanation = BalanceEngine.get_balance_explanation(id, from_user_id, to_user_id)

        return Response({
            "balance": str(explanation["balance"]),
            "expense_breakdown": [
                {
                    "expense_id": str(item["expense_id"]),
                    "description": item["description"],
                    "date": str(item["date"]),
                    "original_amount": str(item["original_amount"]),
                    "currency": item["currency"],
                    "amount": str(item["amount"])
                } for item in explanation["expense_breakdown"]
            ],
            "settlement_breakdown": [
                {
                    "settlement_id": str(item["settlement_id"]),
                    "date": str(item["date"]),
                    "original_amount": str(item["original_amount"]),
                    "currency": item["currency"],
                    "amount": str(item["amount"]),
                    "from_user_id": str(item["from_user_id"]),
                    "to_user_id": str(item["to_user_id"])
                } for item in explanation["settlement_breakdown"]
            ]
        }, status=status.HTTP_200_OK)

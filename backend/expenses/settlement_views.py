from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Settlement
from .services import SettlementService
from .settlement_serializers import CreateSettlementSerializer, SettlementSerializer
from .permissions import IsGroupMember

class CreateSettlementView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        if not group_id:
            return Response({"detail": "group_id query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check active membership
        from groups.models import Membership
        is_member = Membership.objects.filter(
            group_id=group_id,
            user=request.user,
            left_at__isnull=True
        ).exists()
        if not is_member:
            return Response({"detail": "You do not have access to this group's settlements."}, status=status.HTTP_403_FORBIDDEN)

        settlements = Settlement.objects.filter(
            group_id=group_id,
            is_deleted=False
        ).select_related(
            'from_user',
            'to_user',
            'group'
        )
        serializer = SettlementSerializer(settlements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateSettlementSerializer(data=request.data)
        if serializer.is_valid():
            try:
                validated_data = serializer.validated_data
                
                settlement = SettlementService.create_settlement(
                    group_id=validated_data['group_id'],
                    from_user_id=validated_data['from_user_id'],
                    to_user_id=validated_data['to_user_id'],
                    original_amount=validated_data['amount'],
                    currency=validated_data['currency'],
                    settlement_date=validated_data['settlement_date'],
                    source="MANUAL"
                )
                
                # Fetch with optimized select_related
                settlement_fetched = Settlement.objects.select_related(
                    'from_user',
                    'to_user',
                    'group',
                    'group__created_by'
                ).get(pk=settlement.id)
                
                output_serializer = SettlementSerializer(settlement_fetched)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
                
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
                elif hasattr(e, 'messages'):
                    return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SettlementDetailView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request, id):
        try:
            # select_related for optimized query, and filtering out soft-deleted records
            settlement = Settlement.objects.select_related(
                'from_user',
                'to_user',
                'group',
                'group__created_by'
            ).filter(is_deleted=False).get(pk=id)
        except (Settlement.DoesNotExist, ValueError):
            return Response({"detail": "Settlement not found."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = SettlementSerializer(settlement)
        return Response(serializer.data, status=status.HTTP_200_OK)

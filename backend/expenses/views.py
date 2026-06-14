from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Expense
from .services import ExpenseService
from .serializers import CreateExpenseSerializer, ExpenseSerializer
from .permissions import IsGroupMember

class CreateExpenseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateExpenseSerializer(data=request.data)
        if serializer.is_valid():
            try:
                validated_data = serializer.validated_data
                
                # Transform participants payload into splits required by the service
                participants = validated_data['participants']
                splits = []
                for p in participants:
                    splits.append({
                        'user_id': p['user_id'],
                        'share_value': p.get('split_input_value') or Decimal('1.00')
                    })
                
                expense = ExpenseService.create_expense(
                    group_id=validated_data['group_id'],
                    description=validated_data['description'],
                    date=validated_data['date'],
                    original_amount=validated_data['original_amount'],
                    currency=validated_data['currency'],
                    split_type=validated_data['split_type'],
                    created_by=request.user,
                    contributors=validated_data['contributors'],
                    splits=splits,
                    source="MANUAL"
                )
                
                # Retrieve with optimized query mapping to avoid N+1 issues
                expense_fetched = Expense.objects.select_related(
                    'created_by',
                    'group',
                    'group__created_by'
                ).prefetch_related(
                    'contributions__user',
                    'splits__user',
                    'group__memberships__user'
                ).get(pk=expense.id)
                
                output_serializer = ExpenseSerializer(expense_fetched)
                return Response(output_serializer.data, status=status.HTTP_201_CREATED)
                
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)
                elif hasattr(e, 'messages'):
                    return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get(self, request, id):
        try:
            # Optimize query mapping to fetch all nested detail fields (DRF serializers need them)
            expense = Expense.objects.filter(is_deleted=False).select_related(
                'created_by',
                'group',
                'group__created_by'
            ).prefetch_related(
                'contributions__user',
                'splits__user',
                'group__memberships__user'
            ).get(pk=id)
        except (Expense.DoesNotExist, ValidationError):
            return Response({"detail": "Expense not found."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = ExpenseSerializer(expense)
        return Response(serializer.data, status=status.HTTP_200_OK)

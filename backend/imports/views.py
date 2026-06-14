from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from groups.models import Group
from expenses.permissions import IsGroupMember
from .serializers import ImportUploadSerializer
from .services import CSVImportService
from .anomaly_engine import AnomalyDetectionEngine
from .models import ImportBatch

class ImportUploadView(APIView):
    permission_classes = [IsAuthenticated, IsGroupMember]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = ImportUploadSerializer(data=request.data)
        if serializer.is_valid():
            group_id = serializer.validated_data['group_id']
            file_obj = serializer.validated_data['file']

            try:
                group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                return Response({"group_id": ["Group does not exist."]}, status=status.HTTP_400_BAD_REQUEST)

            # Create batch staging metadata
            batch = CSVImportService.create_batch(group, request.user, file_obj.name)

            # Parse CSV rows into staging tables
            rows_imported, status_str = CSVImportService.parse_csv(batch, file_obj)

            return Response({
                "batch_id": str(batch.id),
                "rows_imported": rows_imported,
                "status": status_str
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnomalyDetectView(APIView):
    """POST /api/imports/<batch_id>/detect/ — trigger anomaly detection on a batch."""
    permission_classes = [IsAuthenticated]

    def post(self, request, batch_id):
        try:
            batch = ImportBatch.objects.select_related("group").get(pk=batch_id)
        except (ImportBatch.DoesNotExist, Exception):
            return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the uploader or a group member may trigger detection
        from groups.models import Membership
        is_member = Membership.objects.filter(
            group=batch.group, user=request.user, left_at__isnull=True
        ).exists()
        if not is_member and batch.uploaded_by != request.user:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        engine = AnomalyDetectionEngine()
        result = engine.detect_batch_anomalies(batch.id)
        return Response(result, status=status.HTTP_200_OK)

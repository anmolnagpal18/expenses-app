from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError

from groups.models import Group
from expenses.permissions import IsGroupMember
from .serializers import (
    ImportUploadSerializer,
    ImportBatchDetailSerializer,
    ResolveAnomalyInputSerializer
)
from .services import CSVImportService, ImportResolutionService
from .anomaly_engine import AnomalyDetectionEngine
from .models import ImportBatch, ImportRow

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


class ImportBatchDetailView(APIView):
    """GET /api/imports/batches/<uuid:batch_id>/ — retrieve batch details, rows, anomalies, and resolutions."""
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        try:
            # Prefetch rows, their anomalies, and resolutions for performance
            batch = (
                ImportBatch.objects
                .select_related("group", "uploaded_by")
                .prefetch_related(
                    "rows__anomalies__resolution__resolved_by",
                    "rows__anomalies__row"
                )
                .get(pk=batch_id)
            )
        except (ImportBatch.DoesNotExist, Exception):
            return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

        from groups.models import Membership
        is_member = Membership.objects.filter(
            group=batch.group, user=request.user, left_at__isnull=True
        ).exists()
        if not is_member and batch.uploaded_by != request.user:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ImportBatchDetailSerializer(batch)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResolveAnomalyView(APIView):
    """POST /api/imports/rows/<uuid:row_id>/resolve/ — submit resolution for a row/anomaly."""
    permission_classes = [IsAuthenticated]

    def post(self, request, row_id):
        serializer = ResolveAnomalyInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            ImportResolutionService.resolve_row_anomaly(
                row_id=row_id,
                anomaly_id=serializer.validated_data.get('anomaly_id'),
                user=request.user,
                action_taken=serializer.validated_data['action_taken'],
                notes=serializer.validated_data.get('notes'),
                resolution_details=serializer.validated_data.get('resolution_details')
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            if hasattr(e, 'message_dict'):
                msg = e.message_dict
            elif hasattr(e, 'messages'):
                msg = e.messages[0] if e.messages else str(e)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Anomaly resolved successfully."}, status=status.HTTP_200_OK)


class CommitBatchView(APIView):
    """POST /api/imports/batches/<uuid:batch_id>/commit/ — commit batch and migrate staging to production."""
    permission_classes = [IsAuthenticated]

    def post(self, request, batch_id):
        try:
            batch = ImportBatch.objects.select_related("group").get(pk=batch_id)
        except (ImportBatch.DoesNotExist, Exception):
            return Response({"detail": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

        from groups.models import Membership
        is_member = Membership.objects.filter(
            group=batch.group, user=request.user, left_at__isnull=True
        ).exists()
        if not is_member and batch.uploaded_by != request.user:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            committed_batch = ImportResolutionService.commit_batch(batch_id=batch.id, user=request.user)
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            if hasattr(e, 'message_dict'):
                msg = e.message_dict
            elif hasattr(e, 'messages'):
                msg = e.messages[0] if e.messages else str(e)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "detail": "Batch committed successfully.",
            "import_summary": committed_batch.import_summary
        }, status=status.HTTP_200_OK)


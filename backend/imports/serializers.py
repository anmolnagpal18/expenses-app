from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ImportBatch, ImportRow, ImportAnomaly, ImportResolution

class ImportUploadSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    file = serializers.FileField()

    def validate_file(self, value):
        # Enforce that the uploaded file is a CSV and is not empty
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV.")
        if value.size == 0:
            raise serializers.ValidationError("File cannot be empty.")
        return value


class ImportResolutionSerializer(serializers.ModelSerializer):
    resolved_by_email = serializers.EmailField(source='resolved_by.email', read_only=True)

    class Meta:
        model = ImportResolution
        fields = [
            'id', 'action_taken', 'notes', 'resolution_details',
            'resolved_by_email', 'resolved_at'
        ]


class ImportAnomalySerializer(serializers.ModelSerializer):
    resolution = ImportResolutionSerializer(read_only=True)

    class Meta:
        model = ImportAnomaly
        fields = [
            'id', 'row', 'anomaly_type', 'severity', 'description',
            'is_resolved', 'metadata', 'resolution'
        ]


class ImportRowSerializer(serializers.ModelSerializer):
    anomalies = ImportAnomalySerializer(many=True, read_only=True)

    class Meta:
        model = ImportRow
        fields = [
            'id', 'row_number', 'raw_data', 'status',
            'processing_notes', 'anomalies'
        ]


class ImportBatchDetailSerializer(serializers.ModelSerializer):
    rows = ImportRowSerializer(many=True, read_only=True)
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    filename = serializers.CharField(source='original_filename', read_only=True)
    anomalies = ImportAnomalySerializer(many=True, read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            'id', 'group', 'uploaded_by', 'uploaded_by_email',
            'group_name', 'uploaded_by_username', 'filename',
            'original_filename', 'status', 'total_rows',
            'import_summary', 'uploaded_at', 'approved_at', 'rows', 'anomalies'
        ]


class ResolveAnomalyInputSerializer(serializers.Serializer):
    anomaly_id = serializers.UUIDField(required=False, allow_null=True)
    action_taken = serializers.ChoiceField(
        choices=ImportResolution.ACTION_CHOICES + (('APPROVE', 'Approve'),)
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    resolution_details = serializers.JSONField(required=False, default=dict)

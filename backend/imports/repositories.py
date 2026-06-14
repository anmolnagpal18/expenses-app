from django.core.exceptions import ValidationError
from .models import ImportBatch, ImportRow, ImportAnomaly, ImportResolution

class ImportBatchRepository:
    @staticmethod
    def get_by_id(batch_id):
        try:
            return ImportBatch.objects.get(pk=batch_id)
        except (ImportBatch.DoesNotExist, ValueError, ValidationError):
            return None

    @staticmethod
    def create_batch(group, uploaded_by, original_filename, status='PENDING'):
        return ImportBatch.objects.create(
            group=group,
            uploaded_by=uploaded_by,
            original_filename=original_filename,
            status=status
        )

    @staticmethod
    def update_status(batch_id, new_status):
        batch = ImportBatchRepository.get_by_id(batch_id)
        if batch:
            batch.status = new_status
            batch.save()
        return batch

    @staticmethod
    def get_group_batches(group_id):
        return ImportBatch.objects.filter(group_id=group_id)


class ImportRowRepository:
    @staticmethod
    def get_by_id(row_id):
        try:
            return ImportRow.objects.get(pk=row_id)
        except (ImportRow.DoesNotExist, ValueError, ValidationError):
            return None

    @staticmethod
    def create_row(batch, row_number, raw_data, status='PENDING', processing_notes=None):
        notes = processing_notes if processing_notes is not None else []
        return ImportRow.objects.create(
            batch=batch,
            row_number=row_number,
            raw_data=raw_data,
            status=status,
            processing_notes=notes
        )

    @staticmethod
    def bulk_create_rows(rows):
        return ImportRow.objects.bulk_create(rows)

    @staticmethod
    def get_batch_rows(batch_id):
        return ImportRow.objects.filter(batch_id=batch_id)

    @staticmethod
    def update_status(row_id, new_status):
        row = ImportRowRepository.get_by_id(row_id)
        if row:
            row.status = new_status
            row.save()
        return row


class ImportAnomalyRepository:
    @staticmethod
    def get_by_id(anomaly_id):
        try:
            return ImportAnomaly.objects.get(pk=anomaly_id)
        except (ImportAnomaly.DoesNotExist, ValueError, ValidationError):
            return None

    @staticmethod
    def create_anomaly(batch, row, anomaly_type, severity, description):
        return ImportAnomaly.objects.create(
            batch=batch,
            row=row,
            anomaly_type=anomaly_type,
            severity=severity,
            description=description
        )

    @staticmethod
    def bulk_create_anomalies(anomalies):
        return ImportAnomaly.objects.bulk_create(anomalies)

    @staticmethod
    def get_row_anomalies(row_id):
        return ImportAnomaly.objects.filter(row_id=row_id)

    @staticmethod
    def get_batch_anomalies(batch_id):
        return ImportAnomaly.objects.filter(batch_id=batch_id)


class ImportResolutionRepository:
    @staticmethod
    def get_by_id(resolution_id):
        try:
            return ImportResolution.objects.get(pk=resolution_id)
        except (ImportResolution.DoesNotExist, ValueError, ValidationError):
            return None

    @staticmethod
    def create_resolution(anomaly, resolved_by, action_taken, notes=None):
        return ImportResolution.objects.create(
            anomaly=anomaly,
            resolved_by=resolved_by,
            action_taken=action_taken,
            notes=notes
        )

    @staticmethod
    def get_anomaly_resolution(anomaly_id):
        try:
            return ImportResolution.objects.get(anomaly_id=anomaly_id)
        except (ImportResolution.DoesNotExist, ValueError, ValidationError):
            return None

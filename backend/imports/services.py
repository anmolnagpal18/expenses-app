import csv
import io
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import ImportBatch, ImportRow, ImportAnomaly

class CSVImportService:
    CSV_SCHEMA = {
        "date": ["date", "expense_date"],
        "description": ["description", "expense", "title"],
        "amount": ["amount", "value"],
        "currency": ["currency"],
        "paid_by": ["paid_by", "paid by", "payer"],
        "participants": ["participants", "split_between"],
        "split_type": ["split_type", "split type", "type", "split_strategy"],
        "split_values": ["split_values", "split values", "shares", "percentages", "values", "split_value"],
        "notes": ["notes", "comment", "memo"]
    }

    @staticmethod
    def create_batch(group, uploaded_by, original_filename):
        return ImportBatch.objects.create(
            group=group,
            uploaded_by=uploaded_by,
            original_filename=original_filename,
            status='PENDING'
        )

    @staticmethod
    @transaction.atomic
    def parse_csv(batch, file_obj):
        content = file_obj.read()
        if isinstance(content, bytes):
            content_str = content.decode('utf-8-sig', errors='replace')
        else:
            content_str = content

        csv_file = io.StringIO(content_str)
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            fieldnames = []
        else:
            fieldnames = [h.lower().strip() for h in reader.fieldnames if h]

        # Header Validation
        missing_required = []
        header_mapping = {}

        for standard_name, aliases in CSVImportService.CSV_SCHEMA.items():
            matched_header = None
            for alias in aliases:
                if alias in fieldnames:
                    # Find the original header name from DictReader.fieldnames
                    for original in reader.fieldnames:
                        if original and original.lower().strip() == alias:
                            matched_header = original
                            break
                    if matched_header:
                        break
            if not matched_header:
                missing_required.append(standard_name)
            else:
                header_mapping[standard_name] = matched_header

        # If any of the required columns are missing, fail validation
        if missing_required:
            batch.status = 'REVIEW_REQUIRED'
            batch.total_rows = 0
            batch.save()

            ImportAnomaly.objects.create(
                batch=batch,
                row=None,
                anomaly_type='MISSING_HEADERS',
                severity='ERROR',
                description=f"Missing required columns: {', '.join(missing_required)}",
                is_resolved=False
            )
            return 0, 'REVIEW_REQUIRED'

        # Parse and store rows
        rows_to_create = []
        for idx, row_dict in enumerate(reader, start=1):
            rows_to_create.append(
                ImportRow(
                    batch=batch,
                    row_number=idx,
                    raw_data=row_dict,
                    status='PENDING',
                    processing_notes=["CSV parsed successfully"]
                )
            )

        if rows_to_create:
            ImportRow.objects.bulk_create(rows_to_create)
            batch.total_rows = len(rows_to_create)
            batch.status = 'PENDING'
            batch.save()
        else:
            # Empty file rows
            batch.status = 'PENDING'
            batch.total_rows = 0
            batch.save()

        return batch.total_rows, batch.status

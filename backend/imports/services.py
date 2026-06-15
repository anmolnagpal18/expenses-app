import csv
import io
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import ImportBatch, ImportRow, ImportAnomaly

class CSVImportService:
    CSV_SCHEMA = {
        "date": ["date", "expense_date", "expense date"],
        "description": ["description", "expense", "title"],
        "amount": ["amount", "value"],
        "currency": ["currency"],
        "paid_by": ["paid_by", "paid by", "payer"],
        "participants": ["participants", "split_between", "split between", "split_with", "split with", "members", "split_members", "split members"],
        "split_type": ["split_type", "split type", "type", "split_strategy", "split strategy"],
        "split_values": ["split_values", "split values", "shares", "percentages", "values", "split_value", "split value"],
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
                if standard_name not in ["split_values", "notes"]:
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
            normalized_row = {}
            for std_name, original_header in header_mapping.items():
                normalized_row[std_name] = (row_dict.get(original_header) or "").strip()
            # Keep other headers
            for k, v in row_dict.items():
                if k and k not in header_mapping.values():
                    normalized_row[k] = (v or "").strip()
            rows_to_create.append(
                ImportRow(
                    batch=batch,
                    row_number=idx,
                    raw_data=normalized_row,
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


class ImportResolutionService:
    @staticmethod
    def resolve_user_for_name(row, name, group):
        from django.contrib.auth import get_user_model
        from groups.models import Membership
        User = get_user_model()
        name_clean = name.strip()
        
        # 1. Look for a resolved UNKNOWN_MEMBER anomaly for this name on this row
        anomalies = row.anomalies.filter(anomaly_type="UNKNOWN_MEMBER", is_resolved=True)
        for anomaly in anomalies:
            missing_member = anomaly.metadata.get("missing_member", "")
            if missing_member.strip().lower() == name_clean.lower():
                if hasattr(anomaly, 'resolution'):
                    res = anomaly.resolution
                    if res.action_taken == 'MAP_USER':
                        user_id = res.resolution_details.get("user_id")
                        return User.objects.get(pk=user_id)
                    elif res.action_taken == 'CREATE_USER':
                        email = res.resolution_details.get("email")
                        full_name = res.resolution_details.get("full_name") or name_clean
                        
                        # Create User (minimal)
                        email_cleaned = email.lower().strip()
                        try:
                            user = User.objects.get(email=email_cleaned)
                        except User.DoesNotExist:
                            username = email_cleaned.split('@')[0]
                            base_username = username
                            counter = 1
                            while User.objects.filter(username=username).exists():
                                username = f"{base_username}_{counter}"
                                counter += 1
                            from django.utils.crypto import get_random_string
                            user = User.objects.create_user(
                                username=username,
                                email=email_cleaned,
                                full_name=full_name,
                                password=get_random_string(16)
                            )
                        
                        # Create Membership (if not already a member)
                        if not Membership.objects.filter(group=group, user=user, left_at__isnull=True).exists():
                            from .anomaly_engine import _parse_date
                            from datetime import datetime, time
                            raw = row.raw_data
                            date_raw = str(raw.get("date") or raw.get("expense_date") or "").strip()
                            joined_date = _parse_date(date_raw)
                            if not joined_date:
                                joined_date = timezone.now().date()
                            joined_dt = timezone.make_aware(datetime.combine(joined_date, time.min))
                            
                            Membership.objects.create(
                                group=group,
                                user=user,
                                role='MEMBER',
                                joined_at=joined_dt
                            )
                        return user
                        
        # 2. Fuzzy match
        from .anomaly_engine import _fuzzy_match_member, _ascii_fold, _build_member_aliases
        
        member_aliases = {}
        memberships = Membership.objects.filter(group=group).select_related("user")
        for m in memberships:
            u = m.user
            for alias in _build_member_aliases(u):
                member_aliases.setdefault(alias, u)
                
        key = _ascii_fold(name_clean)
        user = member_aliases.get(key) or _fuzzy_match_member(name_clean, member_aliases)
        if user:
            return user
            
        raise ValidationError(f"Could not resolve name '{name}' to any user.")

    @staticmethod
    @transaction.atomic
    def resolve_row_anomaly(row_id, anomaly_id, user, action_taken, notes=None, resolution_details=None):
        from groups.models import Membership
        from django.utils import timezone
        from .models import ImportAnomaly, ImportResolution, ImportRow
        
        try:
            row = ImportRow.objects.select_related("batch__group").get(pk=row_id)
        except ImportRow.DoesNotExist:
            raise ValidationError("Row not found.")
            
        batch = row.batch
        group = batch.group
        
        # Check permissions
        is_member = Membership.objects.filter(
            group=group, user=user, left_at__isnull=True
        ).exists()
        if not is_member and batch.uploaded_by != user:
            raise ValidationError("You do not have permission to resolve anomalies in this batch.")
            
        resolution_details = resolution_details or {}
        
        if not anomaly_id:
            # Direct row-level action (e.g. approving or ignoring clean rows)
            if action_taken == 'APPROVE':
                row.status = 'APPROVED'
            elif action_taken == 'IGNORE':
                row.status = 'REJECTED'
            else:
                raise ValidationError(f"Action '{action_taken}' is not supported for row-level resolution.")
                
            notes_list = list(row.processing_notes or [])
            notes_list.append(f"Row resolved with action {action_taken} by {user.email}.")
            row.processing_notes = notes_list
            row.save()
            
            # Re-evaluate batch
            has_flagged_rows = batch.rows.filter(status="FLAGGED").exists()
            has_unresolved_batch_anomalies = batch.anomalies.filter(row__isnull=True, is_resolved=False).exists()
            if not has_flagged_rows and not has_unresolved_batch_anomalies:
                batch.status = "PENDING"
            else:
                batch.status = "REVIEW_REQUIRED"
            batch.save()
            return None

        # Fetch specific anomaly
        try:
            anomaly = ImportAnomaly.objects.get(pk=anomaly_id, row=row)
        except ImportAnomaly.DoesNotExist:
            raise ValidationError("Anomaly not found on this row.")
            
        # Create or update resolution
        resolution, created = ImportResolution.objects.update_or_create(
            anomaly=anomaly,
            defaults={
                "resolved_by": user,
                "action_taken": action_taken,
                "notes": notes,
                "resolution_details": resolution_details
            }
        )
        
        anomaly.is_resolved = True
        anomaly.save()
        
        notes_list = list(row.processing_notes or [])
        notes_list.append(
            f"Resolved anomaly {anomaly.anomaly_type} with action {action_taken} by {user.email}."
        )
        row.processing_notes = notes_list
        
        # Re-evaluate row status
        row_anomalies = row.anomalies.all()
        all_resolved = not row_anomalies.filter(is_resolved=False).exists()
        
        if all_resolved:
            has_reject = False
            for a in row_anomalies:
                if a.anomaly_type in ["NEGATIVE_AMOUNT", "INVALID_SPLIT"]:
                    has_reject = True
                    break
                if hasattr(a, 'resolution') and a.resolution.action_taken in ["IGNORE", "MERGE"]:
                    has_reject = True
                    break
            
            if has_reject:
                row.status = "REJECTED"
            else:
                row.status = "APPROVED"
        else:
            row.status = "FLAGGED"
            
        row.save()
        
        # Re-evaluate batch status
        has_flagged_rows = batch.rows.filter(status="FLAGGED").exists()
        has_unresolved_batch_anomalies = batch.anomalies.filter(row__isnull=True, is_resolved=False).exists()
        
        if not has_flagged_rows and not has_unresolved_batch_anomalies:
            batch.status = "PENDING"
        else:
            batch.status = "REVIEW_REQUIRED"
            
        batch.save()
        
        return resolution

    @staticmethod
    @transaction.atomic
    def commit_batch(batch_id, user):
        from django.utils import timezone
        from .models import ImportBatch, ImportRow, ImportAnomaly
        from expenses.services import ExpenseService, SettlementService
        from decimal import Decimal
        
        try:
            batch = ImportBatch.objects.select_related("group").get(pk=batch_id)
        except ImportBatch.DoesNotExist:
            raise ValidationError("Batch not found.")
            
        has_flagged_rows = batch.rows.filter(status="FLAGGED").exists()
        has_unresolved = batch.anomalies.filter(is_resolved=False).exclude(row__status="REJECTED").exists()
        if has_flagged_rows or has_unresolved:
            raise ValidationError("Batch has unresolved anomalies or flagged rows. Review all rows first.")
            
        if batch.status in ['APPROVED', 'REJECTED']:
            raise ValidationError(f"Batch has already been processed (status: {batch.status}).")
            
        # We only import rows that are APPROVED. PENDING and REJECTED rows are skipped.
        approved_rows = batch.rows.filter(status="APPROVED")
        rows_imported_count = 0
        
        for row in approved_rows:
            raw = row.raw_data
            
            amount_raw   = str(raw.get("amount")       or raw.get("value")        or "").strip()
            currency     = str(raw.get("currency")     or "").strip().upper()
            description  = str(raw.get("description")  or raw.get("expense")      or raw.get("title") or "").strip()
            date_raw     = str(raw.get("date")         or raw.get("expense_date") or "").strip()
            paid_by_raw  = str(raw.get("paid_by")      or raw.get("paid by")      or raw.get("payer") or "").strip()
            part_raw     = str(raw.get("participants") or raw.get("split_between") or "").strip()
            split_type   = str(raw.get("split_type")   or raw.get("split type")   or raw.get("type") or "").strip().lower()
            split_vals   = str(raw.get("split_values") or raw.get("split values") or raw.get("shares") or "").strip()
            
            from .anomaly_engine import _parse_date, _parse_amount, _split_list
            amount = _parse_amount(amount_raw)
            expense_date = _parse_date(date_raw)
            participants_raw = _split_list(part_raw)
            
            if amount is None or expense_date is None or not paid_by_raw:
                raise ValidationError(f"Row {row.row_number} has invalid or missing date/amount/paid_by.")
                
            payer = ImportResolutionService.resolve_user_for_name(row, paid_by_raw, batch.group)
            
            is_settlement = False
            settlement_anomaly = row.anomalies.filter(anomaly_type="SETTLEMENT_AS_EXPENSE", is_resolved=True).first()
            if settlement_anomaly and hasattr(settlement_anomaly, 'resolution'):
                if settlement_anomaly.resolution.action_taken == "CONVERT_TO_SETTLEMENT":
                    is_settlement = True
                    
            if is_settlement:
                if not participants_raw:
                    raise ValidationError(f"Row {row.row_number} is converted to settlement but lacks payee/participant.")
                payee = ImportResolutionService.resolve_user_for_name(row, participants_raw[0], batch.group)
                
                SettlementService.create_settlement(
                    group_id=batch.group.id,
                    from_user_id=payer.id,
                    to_user_id=payee.id,
                    original_amount=amount,
                    currency=currency,
                    settlement_date=expense_date,
                    source="CSV_IMPORT"
                )
            else:
                resolved_participants = []
                for p_name in participants_raw:
                    p_user = ImportResolutionService.resolve_user_for_name(row, p_name, batch.group)
                    resolved_participants.append(p_user)
                    
                contributors = [{"user_id": payer.id, "amount_paid": amount}]
                
                if split_type == 'equal':
                    splits = [p.id for p in resolved_participants]
                else:
                    val_strings = _split_list(split_vals)
                    parsed_vals = []
                    for vs in val_strings:
                        val = _parse_amount(vs)
                        if val is None:
                            raise ValidationError(f"Row {row.row_number} split value '{vs}' is not a valid number.")
                        parsed_vals.append(val)
                        
                    if len(parsed_vals) != len(resolved_participants):
                        raise ValidationError(f"Row {row.row_number} has mismatch between participant count ({len(resolved_participants)}) and split values count ({len(parsed_vals)}).")
                        
                    splits = [
                        {"user_id": p.id, "share_value": val}
                        for p, val in zip(resolved_participants, parsed_vals)
                    ]
                    
                ExpenseService.create_expense(
                    group_id=batch.group.id,
                    description=description,
                    date=expense_date,
                    original_amount=amount,
                    currency=currency,
                    split_type=split_type if split_type in ["equal", "percentage", "exact", "shares"] else "equal",
                    created_by=user,
                    contributors=contributors,
                    splits=splits,
                    source="CSV_IMPORT"
                )
                
            rows_imported_count += 1
            
        # We will count why rows were rejected
        rejected_rows = batch.rows.filter(status="REJECTED")
        rejected_rows_count = rejected_rows.count()
        
        duplicates_removed = 0
        negative_amount_removed = 0
        zero_amount_removed = 0
        invalid_split_removed = 0
        
        from .anomaly_engine import _parse_date, _parse_amount, _split_list
        
        for r in rejected_rows:
            anoms = r.anomalies.all()
            has_dup = any(a.anomaly_type == "DUPLICATE_EXPENSE" for a in anoms)
            has_invalid_split = any(a.anomaly_type == "INVALID_SPLIT" for a in anoms)
            has_neg = False
            has_zero = False
            
            for a in anoms:
                if a.anomaly_type == "NEGATIVE_AMOUNT":
                    val_str = str(r.raw_data.get("amount") or r.raw_data.get("value") or "").strip()
                    val = _parse_amount(val_str)
                    if val is not None:
                        if val == 0:
                            has_zero = True
                        elif val < 0:
                            has_neg = True
                    else:
                        has_neg = True
            
            if has_dup:
                duplicates_removed += 1
            if has_neg:
                negative_amount_removed += 1
            if has_zero:
                zero_amount_removed += 1
            if has_invalid_split:
                invalid_split_removed += 1

        # Count resolved UNKNOWN_MEMBER anomalies
        resolved_anom_count = batch.anomalies.filter(
            anomaly_type="UNKNOWN_MEMBER", is_resolved=True
        ).count()
        
        # Count fuzzy matched names across approved rows
        fuzzy_resolved_names = set()
        for row in approved_rows:
            raw = row.raw_data
            paid_by_raw = str(raw.get("paid_by") or raw.get("paid by") or raw.get("payer") or "").strip()
            part_raw = str(raw.get("participants") or raw.get("split_between") or "").strip()
            names = [n for n in _split_list(part_raw) + ([paid_by_raw] if paid_by_raw else []) if n]
            
            for name in names:
                try:
                    resolved_user = ImportResolutionService.resolve_user_for_name(row, name, batch.group)
                    if name.strip().lower() != resolved_user.username.lower() and name.strip().lower() != resolved_user.email.lower():
                        fuzzy_resolved_names.add(name.strip().lower())
                except Exception:
                    pass
                    
        unknown_members_resolved = resolved_anom_count + len(fuzzy_resolved_names)
        
        total_anomalies = batch.anomalies.count()
        resolved_anomalies = batch.anomalies.filter(is_resolved=True).count()
        
        batch.import_summary = {
            "rows_total": batch.total_rows,
            "rows_imported": rows_imported_count,
            "rows_rejected": batch.total_rows - rows_imported_count,
            "duplicates_removed": duplicates_removed,
            "negative_amount_removed": negative_amount_removed,
            "zero_amount_removed": zero_amount_removed,
            "invalid_split_removed": invalid_split_removed,
            "unknown_members_resolved": unknown_members_resolved,
            "anomalies_found": total_anomalies,
            "anomalies_resolved": resolved_anomalies
        }
        
        batch.status = "APPROVED"
        batch.approved_at = timezone.now()
        batch.save()
        
        return batch


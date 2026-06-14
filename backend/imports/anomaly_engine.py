"""
Anomaly Detection Engine for staged CSV import rows.
Commit #27 — feat(imports): implement anomaly detection engine

Analyses each ImportRow within a batch and creates ImportAnomaly records
for any rule violations.  Does NOT create production Expense / Settlement
objects — it only operates on staging data.

Detection rules
---------------
1. NEGATIVE_AMOUNT        – amount <= 0 or non-parseable
2. INVALID_CURRENCY       – currency not in the accepted set
3. UNKNOWN_MEMBER         – paid_by / participant cannot be fuzzy-matched to
                            any group member (active or historical)
4. MEMBERSHIP_VIOLATION   – matched user was not a member on the expense date
5. INVALID_SPLIT          – split_values don't reconcile with amount/type
6. SETTLEMENT_AS_EXPENSE  – description heuristically looks like a settlement
7. DUPLICATE_EXPENSE      – identical (date, description, amount) in
                            production expenses, previous import batches,
                            or within the current batch
8. CONFLICTING_DUPLICATE  – same (date, description) but different amount
                            in any of those three sources

Improvements over initial draft
--------------------------------
- ImportAnomaly.metadata JSONField stores structured context for the UI
  and future resolution workflows (possible_matches, duplicate_row, etc.)
- Unknown-member matching is fuzzy: normalised email, display_name,
  first-name, first-name-initial combinations, so "Aisha K" matches
  "Aisha Kapoor <aisha@gmail.com>".
- Duplicate detection checks three sources: current batch, previous
  ImportBatches for the same group, and production Expense records.
- processing_notes on each row are updated with a human-readable
  summary of every anomaly found.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from groups.models import Membership
from expenses.models import Expense, StaticExchangeRate
from .models import ImportAnomaly, ImportBatch, ImportRow


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SETTLEMENT_KEYWORDS = re.compile(
    r"\b(settlement|settle|repay|repaid|paid back|reimburse|reimbursement)\b",
    re.IGNORECASE,
)

VALID_SPLIT_TYPES = {"equal", "percentage", "exact", "shares"}

# Currencies always considered valid regardless of exchange-rate config.
ALWAYS_VALID_CURRENCIES = {
    "INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "CHF",
    "CNY", "HKD", "NZD", "SEK", "NOK", "DKK", "MXN", "ZAR", "BRL",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> Optional[date]:
    """Try multiple date formats; return a date or None."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
                "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _parse_amount(value: str) -> Optional[Decimal]:
    """Parse numeric string, stripping currency symbols / commas."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
    if not cleaned or cleaned == "-":
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _split_list(raw: str) -> List[str]:
    """Split a comma/semicolon-delimited string."""
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[,;]", str(raw)) if p.strip()]


# ---------------------------------------------------------------------------
# Fuzzy name normalisation & matching
# ---------------------------------------------------------------------------

def _ascii_fold(text: str) -> str:
    """Remove diacritics and lower-case."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _name_tokens(name: str) -> list[str]:
    """Split a name string into individual word tokens."""
    return [t for t in re.split(r"[\s\-_]+", _ascii_fold(name)) if t]


def _build_member_aliases(user) -> list[str]:
    """
    Return all normalised alias strings for a user.

    Covers:
      - email (full + username portion before @)
      - full_name / display_name as-is and as tokens
      - first name, last name, first-name + last-initial
      - first-initial + last name
    """
    aliases: set[str] = set()

    email = getattr(user, "email", "") or ""
    if email:
        aliases.add(_ascii_fold(email))
        username = _ascii_fold(email.split("@")[0])
        aliases.add(username)

    for attr in ("full_name", "display_name", "get_full_name"):
        if callable(getattr(user, attr, None)):
            name = user.get_full_name() or ""
        else:
            name = getattr(user, attr, "") or ""
        if not name:
            continue
        aliases.add(_ascii_fold(name))
        tokens = _name_tokens(name)
        if len(tokens) >= 1:
            aliases.add(tokens[0])              # first name only
        if len(tokens) >= 2:
            aliases.add(tokens[-1])             # last name only
            aliases.add(f"{tokens[0]} {tokens[-1]}")   # "first last"
            aliases.add(f"{tokens[0]} {tokens[-1][0]}")  # "first L"
            aliases.add(f"{tokens[0][0]} {tokens[-1]}")  # "F last"

    return [a for a in aliases if a]


def _fuzzy_match_member(raw_name: str, member_aliases: dict[str, object]) -> Optional[object]:
    """
    Try to match `raw_name` against the alias index.
    Returns the User object or None.
    """
    normalised = _ascii_fold(raw_name.strip())
    if normalised in member_aliases:
        return member_aliases[normalised]

    # Try partial: if any member alias is a prefix/suffix of the raw name or vice-versa
    tokens = _name_tokens(raw_name)
    if not tokens:
        return None

    # "Aisha K" -> tokens = ["aisha", "k"] — check if first token matches uniquely
    first_token = tokens[0]
    last_initial = tokens[-1][0] if len(tokens) > 1 else None

    candidates = []
    for alias, user in member_aliases.items():
        alias_tokens = _name_tokens(alias)
        if not alias_tokens:
            continue
        if alias_tokens[0] == first_token:
            if last_initial is None or (
                len(alias_tokens) > 1 and alias_tokens[-1].startswith(last_initial)
            ):
                candidates.append(user)

    # Deduplicate by user id
    seen_ids: set = set()
    unique: list = []
    for u in candidates:
        uid = getattr(u, "pk", id(u))
        if uid not in seen_ids:
            seen_ids.add(uid)
            unique.append(u)

    if len(unique) == 1:
        return unique[0]
    return None


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class AnomalyDetectionEngine:
    """
    Orchestrates anomaly detection for every ImportRow in a batch.

    Usage::

        engine = AnomalyDetectionEngine()
        result = engine.detect_batch_anomalies(batch_id)

    Returns a summary dict::

        {
            "batch_id": str,
            "rows_processed": int,
            "rows_flagged": int,
            "rows_approved": int,
            "anomalies_created": int,
            "batch_status": str,
        }
    """

    def __init__(self):
        self._group = None
        self._member_aliases: dict[str, object] = {}          # alias -> User
        self._member_memberships: dict[int, list] = {}         # user.pk -> [Membership]
        self._valid_currencies: set[str] = set()
        self._production_expenses: list[dict] = []
        self._prior_batch_rows: list[dict] = []               # from older ImportBatches

        # Intra-batch indices built in first pass
        self._batch_fingerprints: dict[tuple, list] = {}      # (date,desc,amount) -> [row_numbers]
        self._batch_desc_keys: dict[tuple, list] = {}         # (date,desc) -> [(amount, row_num)]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @transaction.atomic
    def detect_batch_anomalies(self, batch_id) -> dict:
        batch = ImportBatch.objects.select_related("group").get(pk=batch_id)
        self._setup_context(batch)

        rows = list(ImportRow.objects.filter(batch=batch).order_by("row_number"))
        anomalies_to_create: list[ImportAnomaly] = []
        rows_flagged = 0
        rows_approved = 0

        self._build_batch_fingerprints(rows)

        for row in rows:
            row_anomalies = self._detect_row_anomalies(batch, row)
            anomalies_to_create.extend(row_anomalies)

            notes = list(row.processing_notes)
            if row_anomalies:
                row.status = "FLAGGED"
                notes.append(f"Flagged: {len(row_anomalies)} anomaly(ies) detected")
                for a in row_anomalies:
                    notes.append(f"  • {a.anomaly_type}: {a.description[:120]}")
                rows_flagged += 1
            else:
                row.status = "APPROVED"
                notes.append("Approved: no anomalies detected")
                rows_approved += 1
            row.processing_notes = notes

        ImportRow.objects.bulk_update(rows, ["status", "processing_notes"])

        if anomalies_to_create:
            ImportAnomaly.objects.bulk_create(anomalies_to_create)

        batch.status = "REVIEW_REQUIRED" if rows_flagged > 0 else "PENDING"
        batch.save(update_fields=["status"])

        return {
            "batch_id": str(batch_id),
            "rows_processed": len(rows),
            "rows_flagged": rows_flagged,
            "rows_approved": rows_approved,
            "anomalies_created": len(anomalies_to_create),
            "batch_status": batch.status,
        }

    # ------------------------------------------------------------------
    # Context setup
    # ------------------------------------------------------------------

    def _setup_context(self, batch: ImportBatch) -> None:
        self._group = batch.group

        # --- Build member alias index ---
        memberships = list(
            Membership.objects.filter(group=self._group).select_related("user")
        )
        for m in memberships:
            user = m.user
            for alias in _build_member_aliases(user):
                # First writer wins to avoid clobbering with a different user
                self._member_aliases.setdefault(alias, user)
            self._member_memberships.setdefault(user.pk, []).append(m)

        # --- Valid currencies ---
        self._valid_currencies = set(ALWAYS_VALID_CURRENCIES)
        self._valid_currencies.add(self._group.base_currency.upper())
        for rate in StaticExchangeRate.objects.all():
            self._valid_currencies.add(rate.from_currency.upper())
            self._valid_currencies.add(rate.to_currency.upper())

        # --- Production expenses for duplicate detection ---
        self._production_expenses = list(
            Expense.objects.filter(group=self._group, is_deleted=False)
            .values("date", "description", "original_amount")
        )

        # --- Rows from prior ImportBatches for the same group ---
        prior_rows = (
            ImportRow.objects
            .filter(batch__group=self._group)
            .exclude(batch=batch)
            .values("batch_id", "row_number", "raw_data")
        )
        self._prior_batch_rows = list(prior_rows)

    def _build_batch_fingerprints(self, rows: list[ImportRow]) -> None:
        self._batch_fingerprints = {}
        self._batch_desc_keys = {}

        for row in rows:
            rd = row.raw_data
            exp_date = _parse_date(str(rd.get("date") or rd.get("expense_date") or ""))
            desc = (rd.get("description") or rd.get("expense") or rd.get("title") or "").strip().lower()
            amount = _parse_amount(str(rd.get("amount") or rd.get("value") or ""))

            if exp_date and desc:
                desc_key = (str(exp_date), desc)
                self._batch_desc_keys.setdefault(desc_key, []).append((amount, row.row_number))
                if amount is not None:
                    fp = (str(exp_date), desc, str(amount))
                    self._batch_fingerprints.setdefault(fp, []).append(row.row_number)

    # ------------------------------------------------------------------
    # Row-level orchestrator
    # ------------------------------------------------------------------

    def _detect_row_anomalies(self, batch: ImportBatch, row: ImportRow) -> list[ImportAnomaly]:
        raw = row.raw_data

        amount_raw   = str(raw.get("amount")       or raw.get("value")        or "").strip()
        currency_raw = str(raw.get("currency")     or "").strip().upper()
        desc_raw     = str(raw.get("description")  or raw.get("expense")      or raw.get("title") or "").strip()
        date_raw     = str(raw.get("date")         or raw.get("expense_date") or "").strip()
        paid_by_raw  = str(raw.get("paid_by")      or raw.get("paid by")      or raw.get("payer") or "").strip()
        part_raw     = str(raw.get("participants") or raw.get("split_between") or "").strip()
        split_type   = str(raw.get("split_type")   or raw.get("split type")   or raw.get("type") or "").strip().lower()
        split_vals   = str(raw.get("split_values") or raw.get("split values") or raw.get("shares") or "").strip()

        amount      = _parse_amount(amount_raw)
        expense_date = _parse_date(date_raw)
        participants = _split_list(part_raw)

        anomalies: list[ImportAnomaly] = []
        anomalies += self._detect_negative_amount(batch, row, amount, amount_raw)
        anomalies += self._detect_currency(batch, row, currency_raw)
        anomalies += self._detect_unknown_members(batch, row, paid_by_raw, participants, expense_date)
        anomalies += self._detect_split_errors(batch, row, split_type, split_vals, participants, amount)
        anomalies += self._detect_settlement_pattern(batch, row, desc_raw)
        anomalies += self._detect_duplicates(batch, row, expense_date, desc_raw, amount)
        return anomalies

    # ------------------------------------------------------------------
    # 1. NEGATIVE_AMOUNT
    # ------------------------------------------------------------------

    def _detect_negative_amount(
        self, batch, row, amount: Optional[Decimal], amount_raw: str
    ) -> list[ImportAnomaly]:
        if amount is None:
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="NEGATIVE_AMOUNT", severity="ERROR",
                description=f"Amount '{amount_raw}' is not a valid number.",
                is_resolved=False,
                metadata={"raw_value": amount_raw},
            )]
        if amount <= Decimal("0"):
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="NEGATIVE_AMOUNT", severity="ERROR",
                description=f"Amount must be positive; got {amount}.",
                is_resolved=False,
                metadata={"raw_value": amount_raw, "parsed_value": str(amount)},
            )]
        return []

    # ------------------------------------------------------------------
    # 2. INVALID_CURRENCY
    # ------------------------------------------------------------------

    def _detect_currency(self, batch, row, currency: str) -> list[ImportAnomaly]:
        if not currency:
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="INVALID_CURRENCY", severity="ERROR",
                description="Currency field is empty.",
                is_resolved=False,
                metadata={},
            )]
        if currency not in self._valid_currencies:
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="INVALID_CURRENCY", severity="WARNING",
                description=f"Currency '{currency}' is not recognised.",
                is_resolved=False,
                metadata={
                    "supplied_currency": currency,
                    "valid_currencies": sorted(self._valid_currencies),
                },
            )]
        return []

    # ------------------------------------------------------------------
    # 3 & 4. UNKNOWN_MEMBER / MEMBERSHIP_VIOLATION
    # ------------------------------------------------------------------

    def _detect_unknown_members(
        self, batch, row,
        paid_by: str, participants: list[str], expense_date: Optional[date]
    ) -> list[ImportAnomaly]:
        results: list[ImportAnomaly] = []
        all_names = [n for n in participants + ([paid_by] if paid_by else []) if n]

        seen: set[str] = set()
        for name in all_names:
            key = _ascii_fold(name.strip())
            if key in seen:
                continue
            seen.add(key)

            # Fuzzy match
            user = self._member_aliases.get(key) or _fuzzy_match_member(name, self._member_aliases)

            if user is None:
                # Build possible-matches list from all members
                possible = self._find_possible_matches(name)
                results.append(ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="UNKNOWN_MEMBER", severity="ERROR",
                    description=(
                        f"'{name}' could not be matched to any group member."
                        + (f" Possible matches: {', '.join(possible)}" if possible else "")
                    ),
                    is_resolved=False,
                    metadata={"missing_member": name, "possible_matches": possible},
                ))
                continue

            # 4. Membership-date violation
            if expense_date is not None:
                memberships = self._member_memberships.get(user.pk, [])
                if not self._was_member_on_date(memberships, expense_date):
                    results.append(ImportAnomaly(
                        batch=batch, row=row,
                        anomaly_type="MEMBERSHIP_VIOLATION", severity="WARNING",
                        description=(
                            f"'{name}' ({user.email}) was not a group member on {expense_date}."
                        ),
                        is_resolved=False,
                        metadata={
                            "member_email": user.email,
                            "expense_date": str(expense_date),
                        },
                    ))

        return results

    def _find_possible_matches(self, raw_name: str) -> list[str]:
        """
        Return a list of member emails whose aliases partially match raw_name.
        Used to populate UNKNOWN_MEMBER anomaly metadata.
        """
        first_token = _name_tokens(raw_name)[0] if _name_tokens(raw_name) else ""
        if not first_token:
            return []

        matched_users: dict[int, object] = {}
        for alias, user in self._member_aliases.items():
            alias_tokens = _name_tokens(alias)
            if alias_tokens and alias_tokens[0] == first_token:
                matched_users[user.pk] = user

        return [u.email for u in matched_users.values()]

    @staticmethod
    def _was_member_on_date(memberships: list, check_date: date) -> bool:
        for m in memberships:
            joined = m.joined_at.date() if hasattr(m.joined_at, "date") else m.joined_at
            left   = (m.left_at.date() if hasattr(m.left_at, "date") else m.left_at) if m.left_at else None
            if joined <= check_date and (left is None or check_date <= left):
                return True
        return False

    # ------------------------------------------------------------------
    # 5. INVALID_SPLIT
    # ------------------------------------------------------------------

    def _detect_split_errors(
        self, batch, row,
        split_type: str, split_values_raw: str,
        participants: list[str], amount: Optional[Decimal],
    ) -> list[ImportAnomaly]:
        if not split_type:
            return []

        if split_type not in VALID_SPLIT_TYPES:
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="INVALID_SPLIT", severity="ERROR",
                description=f"Split type '{split_type}' is not valid. Expected one of: {', '.join(sorted(VALID_SPLIT_TYPES))}.",
                is_resolved=False,
                metadata={"supplied_split_type": split_type, "valid_types": sorted(VALID_SPLIT_TYPES)},
            )]

        if split_type == "equal":
            return []

        if not split_values_raw:
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="INVALID_SPLIT", severity="WARNING",
                description=f"Split type is '{split_type}' but split_values is empty.",
                is_resolved=False,
                metadata={"split_type": split_type},
            )]

        raw_values = _split_list(split_values_raw)
        values: list[Decimal] = []
        for v in raw_values:
            parsed = _parse_amount(v)
            if parsed is None:
                return [ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="INVALID_SPLIT", severity="ERROR",
                    description=f"Split value '{v}' is not a valid number.",
                    is_resolved=False,
                    metadata={"invalid_value": v},
                )]
            values.append(parsed)

        results: list[ImportAnomaly] = []

        if participants and len(values) != len(participants):
            results.append(ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="INVALID_SPLIT", severity="WARNING",
                description=(
                    f"Number of split values ({len(values)}) does not match "
                    f"number of participants ({len(participants)})."
                ),
                is_resolved=False,
                metadata={"split_count": len(values), "participant_count": len(participants)},
            ))

        if split_type == "percentage":
            total_pct = sum(values)
            if abs(total_pct - Decimal("100")) > Decimal("0.01"):
                results.append(ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="INVALID_SPLIT", severity="ERROR",
                    description=f"Percentage values sum to {total_pct}%, expected 100%.",
                    is_resolved=False,
                    metadata={"expected_percentage": 100, "actual_percentage": float(total_pct)},
                ))

        elif split_type == "exact" and amount is not None:
            total_exact = sum(values)
            if abs(total_exact - amount) > Decimal("0.01"):
                results.append(ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="INVALID_SPLIT", severity="ERROR",
                    description=f"Exact split values sum to {total_exact} but amount is {amount}.",
                    is_resolved=False,
                    metadata={"expected_sum": str(amount), "actual_sum": str(total_exact)},
                ))

        return results

    # ------------------------------------------------------------------
    # 6. SETTLEMENT_AS_EXPENSE
    # ------------------------------------------------------------------

    def _detect_settlement_pattern(self, batch, row, description: str) -> list[ImportAnomaly]:
        if SETTLEMENT_KEYWORDS.search(description):
            return [ImportAnomaly(
                batch=batch, row=row,
                anomaly_type="SETTLEMENT_AS_EXPENSE", severity="WARNING",
                description=(
                    f"Description '{description}' looks like a settlement payment. "
                    "Consider converting to a Settlement record."
                ),
                is_resolved=False,
                metadata={"description": description},
            )]
        return []

    # ------------------------------------------------------------------
    # 7 & 8. DUPLICATE_EXPENSE / CONFLICTING_DUPLICATE
    #
    # Sources checked (in order):
    #   A. Production Expense records
    #   B. Rows in previous ImportBatches (same group)
    #   C. Other rows within this batch (intra-batch)
    # ------------------------------------------------------------------

    def _detect_duplicates(
        self, batch, row,
        expense_date: Optional[date], description: str, amount: Optional[Decimal],
    ) -> list[ImportAnomaly]:
        if not expense_date or not description:
            return []

        date_str  = str(expense_date)
        desc_lower = description.lower().strip()

        # --- A. Production expenses ---
        for ex in self._production_expenses:
            ex_date  = str(ex["date"])
            ex_desc  = str(ex["description"]).lower().strip()
            ex_amt   = Decimal(str(ex["original_amount"]))
            if ex_date == date_str and ex_desc == desc_lower:
                if amount is not None and abs(ex_amt - amount) < Decimal("0.01"):
                    return [ImportAnomaly(
                        batch=batch, row=row,
                        anomaly_type="DUPLICATE_EXPENSE", severity="WARNING",
                        description=(
                            f"Matches existing production expense: '{description}' "
                            f"on {expense_date} for {amount}."
                        ),
                        is_resolved=False,
                        metadata={"source": "production", "duplicate_amount": str(amount)},
                    )]
                else:
                    return [ImportAnomaly(
                        batch=batch, row=row,
                        anomaly_type="CONFLICTING_DUPLICATE", severity="ERROR",
                        description=(
                            f"Same date/description as production expense '{description}' "
                            f"on {expense_date} but different amount ({amount} vs {ex_amt})."
                        ),
                        is_resolved=False,
                        metadata={
                            "source": "production",
                            "existing_amount": str(ex_amt),
                            "incoming_amount": str(amount),
                        },
                    )]

        # --- B. Previous ImportBatch rows ---
        for prior in self._prior_batch_rows:
            rd = prior.get("raw_data") or {}
            p_date  = _parse_date(str(rd.get("date") or rd.get("expense_date") or ""))
            p_desc  = (rd.get("description") or rd.get("expense") or rd.get("title") or "").strip().lower()
            p_amt   = _parse_amount(str(rd.get("amount") or rd.get("value") or ""))
            if p_date and str(p_date) == date_str and p_desc == desc_lower:
                if amount is not None and p_amt is not None and abs(p_amt - amount) < Decimal("0.01"):
                    return [ImportAnomaly(
                        batch=batch, row=row,
                        anomaly_type="DUPLICATE_EXPENSE", severity="WARNING",
                        description=(
                            f"Matches a row from a previous import batch: "
                            f"'{description}' on {expense_date} for {amount}."
                        ),
                        is_resolved=False,
                        metadata={
                            "source": "prior_batch",
                            "prior_batch_id": str(prior.get("batch_id")),
                            "prior_row_number": prior.get("row_number"),
                        },
                    )]
                else:
                    return [ImportAnomaly(
                        batch=batch, row=row,
                        anomaly_type="CONFLICTING_DUPLICATE", severity="ERROR",
                        description=(
                            f"Same date/description as a row in a previous import batch "
                            f"('{description}' on {expense_date}) but different amount "
                            f"({amount} vs {p_amt})."
                        ),
                        is_resolved=False,
                        metadata={
                            "source": "prior_batch",
                            "prior_batch_id": str(prior.get("batch_id")),
                            "existing_amount": str(p_amt),
                            "incoming_amount": str(amount),
                        },
                    )]

        # --- C. Intra-batch duplicates ---
        results: list[ImportAnomaly] = []

        if amount is not None:
            fp = (date_str, desc_lower, str(amount))
            matching = self._batch_fingerprints.get(fp, [])
            if len(matching) > 1 and matching[0] != row.row_number:
                results.append(ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="DUPLICATE_EXPENSE", severity="WARNING",
                    description=(
                        f"Duplicate of row #{matching[0]} within this batch: "
                        f"'{description}' on {expense_date} for {amount}."
                    ),
                    is_resolved=False,
                    metadata={"source": "intra_batch", "duplicate_row": matching[0]},
                ))

        desc_key = (date_str, desc_lower)
        entries = self._batch_desc_keys.get(desc_key, [])
        if entries and amount is not None and not results:
            conflicting_amounts = [
                (a, rn) for a, rn in entries
                if rn != row.row_number and a is not None and abs(a - amount) > Decimal("0.01")
            ]
            if conflicting_amounts:
                other_amt, other_rn = conflicting_amounts[0]
                results.append(ImportAnomaly(
                    batch=batch, row=row,
                    anomaly_type="CONFLICTING_DUPLICATE", severity="ERROR",
                    description=(
                        f"Conflicts with row #{other_rn} in this batch — same date/description "
                        f"'{description}' on {expense_date} but different amount "
                        f"({amount} vs {other_amt})."
                    ),
                    is_resolved=False,
                    metadata={
                        "source": "intra_batch",
                        "conflicting_row": other_rn,
                        "existing_amount": str(other_amt),
                        "incoming_amount": str(amount),
                    },
                ))

        return results

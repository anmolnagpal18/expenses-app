from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from collections import defaultdict
from django.contrib.auth import get_user_model
from groups.models import Membership
from .repositories import ExpenseRepository, SettlementRepository

User = get_user_model()

class BalanceEngine:
    """
    Direct Bilateral Balance Calculation Engine.
    Computes active debts between group members from expenses and settlements.
    Prioritizes traceability by saving transaction breakdowns for balance explanations.
    """
    def __init__(self, group_id):
        self.group_id = group_id
        self.balances = []
        # Maps (from_user_id, to_user_id) -> {"amount": Decimal, "expenses": [...], "settlements": [...]}
        self.explanation_map = {}
        self._calculate()

    @classmethod
    def calculate_group_balances(cls, group_id):
        engine = cls(group_id)
        return {"balances": engine.balances}

    @classmethod
    def calculate_user_balance(cls, group_id, user_id):
        engine = cls(group_id)
        owes = []
        owed_by = []
        for bal in engine.balances:
            if bal["from_user_id"] == user_id:
                owes.append({
                    "to_user_id": bal["to_user_id"],
                    "amount": bal["amount"]
                })
            elif bal["to_user_id"] == user_id:
                owed_by.append({
                    "from_user_id": bal["from_user_id"],
                    "amount": bal["amount"]
                })
        return {
            "owes": owes,
            "owed_by": owed_by
        }

    @classmethod
    def get_balance_explanation(cls, group_id, from_user_id, to_user_id):
        engine = cls(group_id)
        explanation = engine.explanation_map.get((from_user_id, to_user_id))
        if explanation:
            return {
                "balance": explanation["amount"],
                "expense_breakdown": explanation["expenses"],
                "settlement_breakdown": explanation["settlements"]
            }
        return {
            "balance": Decimal("0.00"),
            "expense_breakdown": [],
            "settlement_breakdown": []
        }

    def _calculate(self):
        # 1. Fetch group members
        memberships = Membership.objects.filter(group_id=self.group_id)
        user_ids = set(m.user_id for m in memberships)

        # 2. Fetch group transactions (expenses with nested contributions and splits)
        expenses = ExpenseRepository.get_group_expenses_with_relations(self.group_id)
        settlements = SettlementRepository.get_group_settlements(self.group_id)

        # Incorporate user IDs from transactions to verify completeness
        for exp in expenses:
            for c in exp.contributions.all():
                user_ids.add(c.user_id)
            for s in exp.splits.all():
                user_ids.add(s.user_id)
        for setl in settlements:
            user_ids.add(setl.from_user_id)
            user_ids.add(setl.to_user_id)

        user_ids_list = list(user_ids)
        n = len(user_ids_list)

        # Initialize the explanation mapping for all ordered pairs
        for i in range(n):
            for j in range(n):
                if i != j:
                    u1 = user_ids_list[i]
                    u2 = user_ids_list[j]
                    self.explanation_map[(u1, u2)] = {
                        "amount": Decimal("0.00"),
                        "expenses": [],
                        "settlements": []
                    }

        # Track total raw debts: debts[(u1, u2)] = amount u1 owes u2
        debts = defaultdict(Decimal)

        # 3. Calculate expense splits
        for exp in expenses:
            total_amount_base = exp.converted_amount
            if total_amount_base <= 0:
                continue

            # Convert contributions to base currency with remainder correction
            contrib_amounts = {}
            total_contrib_base = Decimal('0.00')
            for c in exp.contributions.all():
                base_amt = (c.amount_paid * exp.exchange_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                contrib_amounts[c.user_id] = base_amt
                total_contrib_base += base_amt

            remainder_contrib = total_amount_base - total_contrib_base
            if remainder_contrib != 0 and exp.contributions.exists():
                first_contrib = exp.contributions.all()[0]
                contrib_amounts[first_contrib.user_id] += remainder_contrib

            # Map split values
            split_amounts = {s.user_id: s.amount_owed for s in exp.splits.all()}

            # Share out participant debts to contributors proportionally
            for i in split_amounts:
                S_i = split_amounts[i]
                if S_i <= 0:
                    continue

                total_allocated = Decimal('0.00')
                participant_allocations = {}
                sorted_contributors = [c.user_id for c in exp.contributions.all()]

                for j_id in sorted_contributors:
                    c_val = contrib_amounts[j_id]
                    allocated = (S_i * c_val / total_amount_base).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                    participant_allocations[j_id] = allocated
                    total_allocated += allocated

                remainder_alloc = S_i - total_allocated
                if remainder_alloc != 0 and sorted_contributors:
                    participant_allocations[sorted_contributors[0]] += remainder_alloc

                # Accumulate split debts
                for j_id, debt_amt in participant_allocations.items():
                    if i != j_id and debt_amt > 0:
                        debts[(i, j_id)] += debt_amt
                        # Log to initial one-way explanation map
                        self.explanation_map[(i, j_id)]["expenses"].append({
                            "expense_id": exp.id,
                            "description": exp.description,
                            "date": exp.date,
                            "original_amount": exp.original_amount,
                            "currency": exp.currency,
                            "amount": debt_amt
                        })

        # 4. Process all settlements
        for setl in settlements:
            from_u = setl.from_user_id
            to_u = setl.to_user_id
            amt = setl.converted_amount

            debts[(from_u, to_u)] -= amt

            # Log to initial one-way explanation map
            self.explanation_map[(from_u, to_u)]["settlements"].append({
                "settlement_id": setl.id,
                "date": setl.settlement_date,
                "original_amount": setl.original_amount,
                "currency": setl.currency,
                "amount": amt,
                "from_user_id": from_u,
                "to_user_id": to_u
            })

        # 5. Net out bilateral balances and assemble final bidirectional explanation map
        for i in range(n):
            for j in range(i + 1, n):
                u1 = user_ids_list[i]
                u2 = user_ids_list[j]

                gross_1_to_2 = debts[(u1, u2)]
                gross_2_to_1 = debts[(u2, u1)]

                net_1_to_2 = gross_1_to_2 - gross_2_to_1

                if net_1_to_2 > 0:
                    self.balances.append({
                        "from_user_id": u1,
                        "to_user_id": u2,
                        "amount": net_1_to_2
                    })
                elif net_1_to_2 < 0:
                    self.balances.append({
                        "from_user_id": u2,
                        "to_user_id": u1,
                        "amount": -net_1_to_2
                    })

                # Bidirectional breakdowns
                # perspective: u1 to u2
                exp_breakdown_1_to_2 = []
                for e in self.explanation_map[(u1, u2)]["expenses"]:
                    exp_breakdown_1_to_2.append(e)
                for e in self.explanation_map[(u2, u1)]["expenses"]:
                    negated_e = e.copy()
                    negated_e["amount"] = -e["amount"]
                    exp_breakdown_1_to_2.append(negated_e)

                setl_breakdown_1_to_2 = []
                for s in self.explanation_map[(u1, u2)]["settlements"]:
                    setl_breakdown_1_to_2.append(s)
                for s in self.explanation_map[(u2, u1)]["settlements"]:
                    negated_s = s.copy()
                    negated_s["amount"] = -s["amount"]
                    setl_breakdown_1_to_2.append(negated_s)

                self.explanation_map[(u1, u2)]["amount"] = net_1_to_2
                self.explanation_map[(u1, u2)]["expenses"] = exp_breakdown_1_to_2
                self.explanation_map[(u1, u2)]["settlements"] = setl_breakdown_1_to_2

                # perspective: u2 to u1
                exp_breakdown_2_to_1 = []
                for e in self.explanation_map[(u2, u1)]["expenses"]:
                    exp_breakdown_2_to_1.append(e)
                for e in self.explanation_map[(u1, u2)]["expenses"]:
                    negated_e = e.copy()
                    negated_e["amount"] = -e["amount"]
                    exp_breakdown_2_to_1.append(negated_e)

                setl_breakdown_2_to_1 = []
                for s in self.explanation_map[(u2, u1)]["settlements"]:
                    setl_breakdown_2_to_1.append(s)
                for s in self.explanation_map[(u1, u2)]["settlements"]:
                    negated_s = s.copy()
                    negated_s["amount"] = -s["amount"]
                    setl_breakdown_2_to_1.append(negated_s)

                self.explanation_map[(u2, u1)]["amount"] = -net_1_to_2
                self.explanation_map[(u2, u1)]["expenses"] = exp_breakdown_2_to_1
                self.explanation_map[(u2, u1)]["settlements"] = setl_breakdown_2_to_1

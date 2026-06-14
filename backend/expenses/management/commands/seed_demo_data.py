import os
import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from groups.models import Group, Membership
from groups.services import GroupService, MembershipService
from expenses.services import ExpenseService, SettlementService
from imports.models import ImportBatch, ImportRow, ImportAnomaly

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds demo data for the Shared Expense Management Application"

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")
        
        # 1. Create Demo Credentials user (demo@splitsmart.com / Demo@123)
        demo_email = "demo@splitsmart.com"
        demo_username = "demo"
        demo_password = "Demo@123"
        
        demo_user, created = User.objects.get_or_create(
            email=demo_email,
            defaults={
                "username": demo_username,
                "full_name": "Demo User",
            }
        )
        if created or not demo_user.check_password(demo_password):
            demo_user.set_password(demo_password)
            demo_user.save()
            self.stdout.write(f"Created/updated demo user: {demo_email} / {demo_password}")

        # 2. Create seed users
        users_data = [
            {"email": "aisha@gmail.com", "username": "aisha", "full_name": "Aisha Kapoor"},
            {"email": "rohan@gmail.com", "username": "rohan", "full_name": "Rohan Mehta"},
            {"email": "priya@gmail.com", "username": "priya", "full_name": "Priya Sharma"},
            {"email": "meera@gmail.com", "username": "meera", "full_name": "Meera Joshi"},
            {"email": "sam@gmail.com", "username": "sam", "full_name": "Sam Wilson"},
            {"email": "dev@gmail.com", "username": "dev", "full_name": "Dev Adiga"},
        ]
        
        users = {}
        for ud in users_data:
            user, created = User.objects.get_or_create(
                email=ud["email"],
                defaults={
                    "username": ud["username"],
                    "full_name": ud["full_name"],
                }
            )
            if created or not user.check_password(demo_password):
                user.set_password(demo_password)
                user.save()
            users[ud["username"]] = user
            self.stdout.write(f"User: {user.username} (PK: {user.id})")

        # 3. Create group Flatmates (Aisha is creator/owner)
        group = Group.objects.filter(name="Flatmates").first()
        if not group:
            group = GroupService.create_group(
                name="Flatmates",
                base_currency="INR",
                creator_user=users["aisha"]
            )
            # Make sure creator's membership starts way in the past
            creator_mem = Membership.objects.filter(group=group, user=users["aisha"]).first()
            if creator_mem:
                creator_mem.joined_at = timezone.now() - timedelta(days=60)
                creator_mem.save()
            self.stdout.write(f"Created group Flatmates (ID: {group.id})")
        else:
            self.stdout.write(f"Group Flatmates already exists (ID: {group.id})")
            creator_mem = Membership.objects.filter(group=group, user=users["aisha"]).first()
            if creator_mem:
                creator_mem.joined_at = timezone.now() - timedelta(days=60)
                creator_mem.save()

        # Ensure demo user is in Flatmates group as ADMIN
        demo_membership = Membership.objects.filter(group=group, user=demo_user).first()
        if not demo_membership:
            demo_membership = MembershipService.add_member(
                group_id=group.id,
                user_id=demo_user.id,
                role="ADMIN",
                joined_at=timezone.now() - timedelta(days=60)
            )
            self.stdout.write("Added demo user as ADMIN to Flatmates group")

        # Add other users to the group
        for username, user_obj in users.items():
            if user_obj == users["aisha"]:
                continue # Already added as creator/owner
            mem = Membership.objects.filter(group=group, user=user_obj).first()
            if not mem:
                mem = MembershipService.add_member(
                    group_id=group.id,
                    user_id=user_obj.id,
                    role="MEMBER",
                    joined_at=timezone.now() - timedelta(days=60)
                )
                self.stdout.write(f"Added member: {username}")
            else:
                mem.joined_at = timezone.now() - timedelta(days=60)
                mem.save()

        # 4. Create Equal Split Expense
        # Aisha pays 600.00 for Internet bill. Split equally between Aisha, Rohan, Priya (200.00 each)
        try:
            ExpenseService.create_expense(
                group_id=group.id,
                description="Internet Bill",
                date=timezone.now() - timedelta(days=10),
                original_amount=Decimal("600.00"),
                currency="INR",
                split_type="equal",
                created_by=users["aisha"],
                contributors=[{"user_id": users["aisha"].id, "amount_paid": Decimal("600.00")}],
                splits=[
                    {"user_id": users["aisha"].id, "share_value": Decimal("1.00")},
                    {"user_id": users["rohan"].id, "share_value": Decimal("1.00")},
                    {"user_id": users["priya"].id, "share_value": Decimal("1.00")},
                ],
                source="SEED"
            )
            self.stdout.write("Created Equal Split Expense: Internet Bill (600.00)")
        except Exception as e:
            self.stdout.write(f"Skipped Equal Expense: {e}")

        # 5. Create Percentage Split Expense
        # Rohan pays 1000.00 for Groceries. Split: Rohan 50%, Priya 30%, Meera 20%
        try:
            ExpenseService.create_expense(
                group_id=group.id,
                description="Groceries",
                date=timezone.now() - timedelta(days=8),
                original_amount=Decimal("1000.00"),
                currency="INR",
                split_type="percentage",
                created_by=users["rohan"],
                contributors=[{"user_id": users["rohan"].id, "amount_paid": Decimal("1000.00")}],
                splits=[
                    {"user_id": users["rohan"].id, "share_value": Decimal("50.00")},
                    {"user_id": users["priya"].id, "share_value": Decimal("30.00")},
                    {"user_id": users["meera"].id, "share_value": Decimal("20.00")},
                ],
                source="SEED"
            )
            self.stdout.write("Created Percentage Split Expense: Groceries (1000.00)")
        except Exception as e:
            self.stdout.write(f"Skipped Percentage Expense: {e}")

        # 6. Create Exact Split Expense
        # Priya pays 1500.00 for Gas + Utilities. Split: Priya 600.00, Meera 500.00, Sam 400.00
        try:
            ExpenseService.create_expense(
                group_id=group.id,
                description="Gas & Electricity",
                date=timezone.now() - timedelta(days=6),
                original_amount=Decimal("1500.00"),
                currency="INR",
                split_type="exact",
                created_by=users["priya"],
                contributors=[{"user_id": users["priya"].id, "amount_paid": Decimal("1500.00")}],
                splits=[
                    {"user_id": users["priya"].id, "share_value": Decimal("600.00")},
                    {"user_id": users["meera"].id, "share_value": Decimal("500.00")},
                    {"user_id": users["sam"].id, "share_value": Decimal("400.00")},
                ],
                source="SEED"
            )
            self.stdout.write("Created Exact Split Expense: Gas & Electricity (1500.00)")
        except Exception as e:
            self.stdout.write(f"Skipped Exact Expense: {e}")

        # 7. Create Shares Split Expense
        # Meera pays 1200.00 for Cleaning Supplies. Split by shares: Meera 3 shares, Sam 2 shares, Dev 1 share.
        try:
            ExpenseService.create_expense(
                group_id=group.id,
                description="Cleaning Supplies",
                date=timezone.now() - timedelta(days=4),
                original_amount=Decimal("1200.00"),
                currency="INR",
                split_type="shares",
                created_by=users["meera"],
                contributors=[{"user_id": users["meera"].id, "amount_paid": Decimal("1200.00")}],
                splits=[
                    {"user_id": users["meera"].id, "share_value": Decimal("3.00")},
                    {"user_id": users["sam"].id, "share_value": Decimal("2.00")},
                    {"user_id": users["dev"].id, "share_value": Decimal("1.00")},
                ],
                source="SEED"
            )
            self.stdout.write("Created Shares Split Expense: Cleaning Supplies (1200.00)")
        except Exception as e:
            self.stdout.write(f"Skipped Shares Expense: {e}")

        # 8. Create One Settlement
        # Rohan settles debt by paying Aisha 150.00
        try:
            SettlementService.create_settlement(
                group_id=group.id,
                from_user_id=users["rohan"].id,
                to_user_id=users["aisha"].id,
                original_amount=Decimal("150.00"),
                currency="INR",
                settlement_date=timezone.now().date() - timedelta(days=2),
                source="SEED"
            )
            self.stdout.write("Created Settlement: Rohan paid Aisha 150.00")
        except Exception as e:
            self.stdout.write(f"Skipped Settlement: {e}")

        # 9. Create Staging Import Batches (Completed & Pending)
        # Create completed batch
        comp_batch = ImportBatch.objects.create(
            group=group,
            uploaded_by=users["aisha"],
            original_filename="historical_jan.csv",
            status="completed",
            import_summary={
                "rows_total": 5,
                "rows_imported": 4,
                "rows_rejected": 1,
                "anomalies_found": 1,
                "anomalies_resolved": 1
            }
        )
        self.stdout.write(f"Created completed ImportBatch (ID: {comp_batch.id})")

        # Create pending batch
        pending_batch = ImportBatch.objects.create(
            group=group,
            uploaded_by=users["meera"],
            original_filename="messy_house_bills.csv",
            status="pending_review"
        )
        self.stdout.write(f"Created pending ImportBatch (ID: {pending_batch.id})")

        # Create staging rows with anomalies
        # Row 1: Normal (Clean row, APPROVED)
        row1 = ImportRow.objects.create(
            batch=pending_batch,
            row_number=1,
            raw_data={
                "date": str(timezone.now().date() - timedelta(days=1)),
                "description": "Weekly milk & bread",
                "amount": "120.00",
                "currency": "INR",
                "split_type": "equal",
                "paid_by": "meera",
                "participants": "meera, sam, dev"
            },
            status="APPROVED"
        )

        # Row 2: Unknown member anomaly (Aisha K is not matched)
        row2 = ImportRow.objects.create(
            batch=pending_batch,
            row_number=2,
            raw_data={
                "date": str(timezone.now().date() - timedelta(days=2)),
                "description": "Curry Night dinner",
                "amount": "900.00",
                "currency": "INR",
                "split_type": "equal",
                "paid_by": "Aisha K",
                "participants": "aisha, rohan, priya"
            },
            status="PENDING"
        )
        ImportAnomaly.objects.create(
            batch=pending_batch,
            row=row2,
            anomaly_type="UNKNOWN_MEMBER",
            severity="ERROR",
            description="Unknown contributor user: 'Aisha K'",
            metadata={"missing_member": "Aisha K", "possible_matches": ["aisha"]}
        )

        # Row 3: Duplicate row anomaly
        row3 = ImportRow.objects.create(
            batch=pending_batch,
            row_number=3,
            raw_data={
                "date": str(timezone.now().date() - timedelta(days=10)),
                "description": "Internet Bill",
                "amount": "600.00",
                "currency": "INR",
                "split_type": "equal",
                "paid_by": "aisha",
                "participants": "aisha, rohan, priya"
            },
            status="PENDING"
        )
        ImportAnomaly.objects.create(
            batch=pending_batch,
            row=row3,
            anomaly_type="DUPLICATE_EXPENSE",
            severity="WARNING",
            description="This row appears to be a duplicate of an existing production expense.",
            metadata={"duplicate_expense_id": "duplicate"}
        )

        self.stdout.write("Demo data seeded successfully!")

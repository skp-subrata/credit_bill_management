import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# Ensure project path is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from database import db
from models import Role, Permission, User, HospitalUnit, Payer, HospitalPayer
from flask import Flask

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def seed_database():
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        # 1. Seed Roles
        roles_data = [
            ("super_admin", "Super Admin", "Full system access across all hospital units"),
            ("admin", "Admin", "Unit-level administrator and billing manager"),
            ("operator", "Operator", "Operational data entry, billing, dispatch & query processing")
        ]

        roles_dict = {}
        for code, name, desc in roles_data:
            role = Role.query.filter_by(role_code=code).first()
            if not role:
                role = Role(role_code=code, role_name=name, description=desc)
                db.session.add(role)
                db.session.flush()
            roles_dict[code] = role

        # 2. Seed Permissions
        permissions_data = [
            ("manage_system", "System Configuration", "System"),
            ("manage_units", "Hospital Units Management", "Masters"),
            ("manage_users", "User Management & RBAC", "Users"),
            ("manage_payers", "Payer & Config Management", "Payers"),
            ("register_patient", "Register & Edit Patient", "Encounters"),
            ("manage_admission", "IP Admission & Discharge", "Encounters"),
            ("manage_op_episode", "OP Episode Registration", "Encounters"),
            ("generate_bill", "Generate IP/OP Bills", "Billing"),
            ("verify_bill", "Verify & Approve Bills", "Billing"),
            ("dispatch_bill", "Dispatch Bill Processing", "Billing"),
            ("manage_query", "Payer Query Handling", "Billing"),
            ("process_payment", "Record Bill Payment", "Billing"),
            ("close_bill", "Close & Archive Bill", "Billing"),
            ("view_reports", "View & Export Reports", "Reports"),
            ("view_audit_logs", "View System Audit Logs", "Audit")
        ]

        perms_objs = []
        for code, name, module in permissions_data:
            perm = Permission.query.filter_by(perm_code=code).first()
            if not perm:
                perm = Permission(perm_code=code, perm_name=name, module=module)
                db.session.add(perm)
                db.session.flush()
            perms_objs.append(perm)

        # Assign all permissions to Super Admin
        super_admin_role = roles_dict["super_admin"]
        super_admin_role.permissions = perms_objs

        # Assign unit admin permissions
        admin_role = roles_dict["admin"]
        admin_role.permissions = [p for p in perms_objs if p.perm_code not in ("manage_system", "manage_units")]

        # Assign operator permissions
        operator_role = roles_dict["operator"]
        operator_role.permissions = [
            p for p in perms_objs if p.perm_code in (
                "register_patient", "manage_admission", "manage_op_episode", 
                "generate_bill", "dispatch_bill", "manage_query", "process_payment", "view_reports"
            )
        ]

        db.session.commit()

        # 3. Seed Hospital Unit
        unit = HospitalUnit.query.filter_by(unit_code="HOSP-MAIN").first()
        if not unit:
            unit = HospitalUnit(
                unit_code="HOSP-MAIN",
                hospital_name="City Central Super Specialty Hospital",
                address_line1="100 Healthcare Boulevard",
                city="Metropolis",
                state="State",
                pincode="500001",
                contact_no="+1-800-555-0199",
                email="contact@citycentralhospital.com",
                status="ACTIVE"
            )
            db.session.add(unit)
            db.session.commit()

        # 4. Seed Super Admin User
        admin_user = User.query.filter_by(employee_id="EMP001").first()
        if not admin_user:
            admin_user = User(
                employee_id="EMP001",
                name="Super Administrator",
                email="admin@hospital.com",
                phone="+1-800-555-0100",
                password_hash=generate_password_hash("admin123"),
                role_id=roles_dict["super_admin"].id,
                hospital_unit_id=unit.unit_id,
                status="ACTIVE"
            )
            db.session.add(admin_user)

        # Seed Operator User
        operator_user = User.query.filter_by(employee_id="EMP002").first()
        if not operator_user:
            operator_user = User(
                employee_id="EMP002",
                name="Billing Operator",
                email="operator@hospital.com",
                phone="+1-800-555-0102",
                password_hash=generate_password_hash("operator123"),
                role_id=roles_dict["operator"].id,
                hospital_unit_id=unit.unit_id,
                status="ACTIVE"
            )
            db.session.add(operator_user)

        db.session.commit()

        # 5. Seed Payers
        payers_data = [
            ("PAY-INS-01", "Star Health Insurance", "INSURANCE", "Insurance Desk", "claims@starhealth.com", "+1-800-222-1111"),
            ("PAY-TPA-01", "Medi Assist TPA", "TPA", "TPA Manager", "tpa@mediassist.com", "+1-800-333-2222"),
            ("PAY-GOV-01", "Central Health Scheme (CGHS)", "GOVERNMENT", "Govt Coordinator", "cghs@gov.in", "+1-800-444-3333")
        ]

        for pcode, pname, ptype, pcontact, pemail, pphone in payers_data:
            payer = Payer.query.filter_by(payer_code=pcode).first()
            if not payer:
                payer = Payer(
                    payer_code=pcode,
                    payer_name=pname,
                    payer_type=ptype,
                    contact_person=pcontact,
                    email=pemail,
                    phone=pphone,
                    status="ACTIVE"
                )
                db.session.add(payer)
                db.session.flush()

                # Add Hospital Payer Config
                hp_config = HospitalPayer(
                    unit_id=unit.unit_id,
                    payer_id=payer.payer_id,
                    payer_code_at_unit=f"UNIT-{pcode}",
                    billing_type="CREDIT",
                    credit_allowed=True,
                    submission_tat_days=15,
                    document_requirement="Pre-Auth Copy, Discharge Summary, Itemized Bill, Diagnostic Reports",
                    approval_required=True,
                    dispatch_mode="COURIER",
                    contact_email=pemail,
                    contact_person=pcontact,
                    status="ACTIVE"
                )
                db.session.add(hp_config)

        db.session.commit()
        print("[SUCCESS] Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()


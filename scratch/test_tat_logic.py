import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from database import db
from models import HospitalPayer, HospitalUnit, Payer
from utils.tat import calculate_tat_start_date, calculate_tat_metrics

def run_test():
    print("==================================================")
    print("TESTING MONTHLY SUBMISSION TAT CALCULATION LOGIC")
    print("==================================================")

    # 1. Verify User Examples against calculate_tat_start_date
    test_cases = [
        ("2026-06-05", True, "2026-07-01"),
        ("2026-06-15", True, "2026-07-01"),
        ("2026-06-30", True, "2026-07-01"),
        ("2026-07-01", True, "2026-08-01"),
        ("2026-07-15", False, "2026-07-15"),
    ]

    print("\n1. Testing TAT Start Date Examples:")
    for build_date, monthly_sub, expected_start in test_cases:
        res_date = calculate_tat_start_date(build_date, monthly_submission=monthly_sub)
        res_str = res_date.strftime('%Y-%m-%d')
        status = "PASSED" if res_str == expected_start else f"FAILED (Got {res_str})"
        print(f"   - Build: {build_date} | Monthly Sub: {monthly_sub:5} => TAT Start: {res_str} [{status}]")
        assert res_str == expected_start, f"Expected {expected_start}, got {res_str}"

    print("\n2. Testing Comprehensive TAT SLA Metrics (15 Days SLA):")
    m1 = calculate_tat_metrics("2026-06-15", submission_tat_days=15, monthly_submission=True)
    print(f"   - Build: 2026-06-15 (Monthly Sub = True):")
    print(f"       TAT Start Date: {m1['tat_start_date']}")
    print(f"       TAT Due Date:   {m1['tat_due_date']}")
    assert m1['tat_start_date'] == "2026-07-01"
    assert m1['tat_due_date'] == "2026-07-16"

    m2 = calculate_tat_metrics("2026-07-15", submission_tat_days=15, monthly_submission=False)
    print(f"   - Build: 2026-07-15 (Monthly Sub = False):")
    print(f"       TAT Start Date: {m2['tat_start_date']}")
    print(f"       TAT Due Date:   {m2['tat_due_date']}")
    assert m2['tat_start_date'] == "2026-07-15"
    assert m2['tat_due_date'] == "2026-07-30"

    # 3. Database Model & Persistence Test
    print("\n3. Testing Database Model Persistence for monthly_submission...")
    with app.app_context():
        db.create_all()
        unit = HospitalUnit.query.first()
        payer = Payer.query.first()

        if unit and payer:
            hp = HospitalPayer.query.filter_by(unit_id=unit.unit_id, payer_id=payer.payer_id).first()
            if not hp:
                hp = HospitalPayer(
                    unit_id=unit.unit_id,
                    payer_id=payer.payer_id,
                    submission_tat_days=15,
                    monthly_submission=True
                )
                db.session.add(hp)
                db.session.commit()
            else:
                hp.monthly_submission = True
                db.session.commit()

            db.session.refresh(hp)
            print(f"   - HospitalPayer ID #{hp.hospital_payer_id} Persistence:")
            print(f"       Unit: {hp.unit_id} | Payer: {hp.payer_id} | Monthly Submission: {hp.monthly_submission}")
            assert hp.monthly_submission is True, "monthly_submission should persist as True"

    print("\n==================================================")
    print("ALL MONTHLY SUBMISSION TAT LOGIC TESTS PASSED!")
    print("==================================================")

if __name__ == '__main__':
    run_test()

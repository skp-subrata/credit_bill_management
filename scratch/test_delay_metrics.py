import sys, os
sys.path.insert(0, os.path.abspath('.'))
from datetime import datetime, timedelta
from app import app
from database import db
from models import Bill, BillDispatch, BillQuery, Patient, HospitalUnit, User
from utils.tat import calculate_bill_delay_metrics

def run_tests():
    print("==================================================")
    print("Testing Focused Delay Tracking Engine (Dispatch & Query Resolution)")
    print("==================================================")

    with app.app_context():
        unit = HospitalUnit.query.first()
        patient = Patient.query.first()
        user = User.query.first()

        ref_today = datetime(2026, 9, 12)

        # Cleanup test bills
        existing = Bill.query.filter(Bill.bill_number.like('BILL-DELAY-TEST-%')).all()
        for b in existing:
            db.session.delete(b)
        db.session.commit()

        # --------------------------------------------------
        # Case 1: Within SLA (Pending Dispatch)
        # --------------------------------------------------
        b1 = Bill(
            bill_number='BILL-DELAY-TEST-01',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-10', # SLA Due: 2026-09-25
            bill_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(b1)
        db.session.commit()
        
        m1 = calculate_bill_delay_metrics(b1, current_date=ref_today)
        print(f"\n[Case 1 - Pending Within SLA] Status: '{m1['dispatch_delay_status']}', Days: {m1['dispatch_delay_days']}, Flag: {m1['dispatch_delay_flag']}")
        assert m1['dispatch_delay_status'] == 'PENDING', f"Expected PENDING, got {m1['dispatch_delay_status']}"
        assert m1['dispatch_delay_flag'] is False
        assert m1['dispatch_delay_days'] == 0

        # --------------------------------------------------
        # Case 2: SLA Crossed & Not Dispatched (Pending Overdue)
        # --------------------------------------------------
        b2 = Bill(
            bill_number='BILL-DELAY-TEST-02',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-08-20', # SLA Due: 2026-09-04, Ref Today: 12-Sep -> 8 Days Delayed
            bill_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(b2)
        db.session.commit()

        m2 = calculate_bill_delay_metrics(b2, current_date=ref_today)
        print(f"[Case 2 - Overdue Pending] Status: '{m2['dispatch_delay_status']}', Days: {m2['dispatch_delay_days']}, Flag: {m2['dispatch_delay_flag']}")
        assert m2['dispatch_delay_status'] == 'DELAYED', f"Expected DELAYED, got {m2['dispatch_delay_status']}"
        assert m2['dispatch_delay_flag'] is True
        assert m2['dispatch_delay_days'] == 8
        assert m2['dispatch_delayed_completed'] is False

        # --------------------------------------------------
        # Case 3: Dispatched Late (Historical Fact Preserved)
        # --------------------------------------------------
        b3 = Bill(
            bill_number='BILL-DELAY-TEST-03',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-08-20', # SLA Due: 2026-09-04
            bill_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(b3)
        db.session.commit()

        # Log dispatch on 12-Sep (4-Sep due date -> 8 days late)
        d3 = BillDispatch(
            bill_id=b3.bill_id,
            bill_number=b3.bill_number,
            dispatch_date='2026-09-12',
            dispatch_mode='COURIER',
            dispatched_by=user.id
        )
        db.session.add(d3)
        b3.update_lifecycle_status() # Sets bill_status = DISPATCHED
        db.session.commit()

        m3 = calculate_bill_delay_metrics(b3, current_date=ref_today)
        print(f"[Case 3 - Dispatched Late] Bill Lifecycle Status: '{b3.bill_status}' | Delay Status: '{m3['dispatch_delay_status']}', Days: {m3['dispatch_delay_days']}, Completed: {m3['dispatch_delayed_completed']}")
        assert b3.bill_status == 'DISPATCHED'
        assert m3['dispatch_delay_status'] == 'DISPATCHED_LATE', f"Expected DISPATCHED_LATE, got {m3['dispatch_delay_status']}"
        assert m3['dispatch_delay_flag'] is True
        assert m3['dispatch_delay_days'] == 8
        assert m3['dispatch_delayed_completed'] is True

        # --------------------------------------------------
        # Case 4: Dispatched On Time
        # --------------------------------------------------
        b4 = Bill(
            bill_number='BILL-DELAY-TEST-04',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-01', # SLA Due: 2026-09-16
            bill_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(b4)
        db.session.commit()

        d4 = BillDispatch(
            bill_id=b4.bill_id,
            bill_number=b4.bill_number,
            dispatch_date='2026-09-12', # Dispatched 12-Sep <= 16-Sep
            dispatch_mode='COURIER',
            dispatched_by=user.id
        )
        db.session.add(d4)
        b4.update_lifecycle_status()
        db.session.commit()

        m4 = calculate_bill_delay_metrics(b4, current_date=ref_today)
        print(f"[Case 4 - Dispatched On Time] Status: '{m4['dispatch_delay_status']}', Days: {m4['dispatch_delay_days']}, Flag: {m4['dispatch_delay_flag']}")
        assert m4['dispatch_delay_status'] == 'ON_TIME'
        assert m4['dispatch_delay_flag'] is False

        # --------------------------------------------------
        # Case 5: Query Resolution Delay Test
        # --------------------------------------------------
        b5 = Bill(
            bill_number='BILL-DELAY-TEST-05',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-01',
            bill_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(b5)
        db.session.commit()

        # Raise query on 2026-09-01 with due date 2026-09-05 (Overdue as of 12-Sep)
        q5 = BillQuery(
            bill_id=b5.bill_id,
            query_code='QRY-TEST-05',
            query_date='2026-09-01',
            query_description='Document missing',
            due_date='2026-09-05',
            query_status='OPEN'
        )
        db.session.add(q5)
        b5.update_lifecycle_status()
        db.session.commit()

        m5 = calculate_bill_delay_metrics(b5, current_date=ref_today)
        print(f"[Case 5 - Query Resolution Delayed] Status: '{m5['query_delay_status']}', Days: {m5['query_delay_days']}, Flag: {m5['query_delay_flag']}")
        assert m5['query_delay_status'] == 'QUERY_DELAYED'
        assert m5['query_delay_days'] == 7
        assert m5['query_delay_flag'] is True

        # Cleanup test bills
        for b in [b1, b2, b3, b4, b5]:
            db.session.delete(b)
        db.session.commit()

    print("\n==================================================")
    print("ALL FOCUSED DELAY TRACKING TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()

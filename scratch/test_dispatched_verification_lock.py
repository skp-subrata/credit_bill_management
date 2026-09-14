import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import app
from database import db
from models import Bill, BillVerification, BillDispatch, Patient, HospitalUnit, User

def run_tests():
    print("==================================================")
    print("Testing Verification Lock for DISPATCHED Bills")
    print("==================================================")

    with app.app_context():
        unit = HospitalUnit.query.first()
        patient = Patient.query.first()
        user = User.query.first()

        if not unit or not patient or not user:
            print("Missing prerequisite unit/patient/user in DB.")
            return

        # Clean up existing test bill
        test_bill = Bill.query.filter_by(bill_number='BILL-TEST-LOCK-001').first()
        if test_bill:
            db.session.delete(test_bill)
            db.session.commit()

        bill = Bill(
            bill_number='BILL-TEST-LOCK-001',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-14',
            bill_amount=10000.0,
            approved_amount=10000.0,
            outstanding_amount=10000.0,
            created_by=user.id
        )
        db.session.add(bill)
        db.session.commit()

        # Step 1: Approve & Verify
        verif = BillVerification(
            bill_id=bill.bill_id,
            verification_status='VERIFIED',
            verified_by=user.id,
            verification_remarks='Approved'
        )
        db.session.add(verif)
        bill.update_lifecycle_status()
        db.session.commit()

        # Step 2: Record Dispatch
        disp = BillDispatch(
            bill_id=bill.bill_id,
            bill_number=bill.bill_number,
            dispatch_date='2026-09-14',
            dispatch_mode='COURIER',
            courier_name='BlueDart',
            tracking_number='BD-998877',
            dispatched_by=user.id
        )
        db.session.add(disp)
        bill.update_lifecycle_status()
        db.session.commit()

        assert bill.effective_dispatch_status == 'DISPATCHED'
        print("[OK] Bill status confirmed as DISPATCHED")

        # Step 3: Attempt to submit Verification action on DISPATCHED bill
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['role_code'] = 'super_admin'

            response = client.post(f'/billing/bills/{bill.bill_id}/verify', data={
                'action': 'REJECT',
                'remarks': 'Attempting post-dispatch rejection'
            }, follow_redirects=True)

            assert b"already been DISPATCHED" in response.data
            print("[OK] Server correctly BLOCKED verification attempt for DISPATCHED bill!")

        # Clean up
        db.session.delete(bill)
        db.session.commit()

    print("==================================================")
    print("ALL DISPATCHED VERIFICATION LOCK TESTS PASSED!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()

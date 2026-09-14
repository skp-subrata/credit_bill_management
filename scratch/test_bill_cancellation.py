import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import app
from database import db
from models import Bill, BillVerification, BillDispatch, Patient, HospitalUnit, User

def run_tests():
    print("==================================================")
    print("Testing Bill Verification Cancellation Flow")
    print("==================================================")

    with app.app_context():
        unit = HospitalUnit.query.first()
        patient = Patient.query.first()
        user = User.query.first()

        if not unit or not patient or not user:
            print("Missing prerequisite unit/patient/user in DB.")
            return

        # Clean up existing test bill
        test_bill = Bill.query.filter_by(bill_number='BILL-TEST-CANCEL-001').first()
        if test_bill:
            db.session.delete(test_bill)
            db.session.commit()

        bill = Bill(
            bill_number='BILL-TEST-CANCEL-001',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-14',
            bill_amount=5000.0,
            approved_amount=5000.0,
            outstanding_amount=5000.0,
            created_by=user.id
        )
        db.session.add(bill)
        db.session.commit()

        # Initial check
        assert bill.bill_status == 'GENERATED'
        print("[OK] Initial Bill Status: GENERATED")

        # Simulate Verification Cancellation
        verif = BillVerification(
            bill_id=bill.bill_id,
            verification_status='CANCELLED',
            verified_by=user.id,
            verification_remarks='Bill cancelled due to incorrect IP admission entry',
            rejection_reason='Incorrect entry'
        )
        db.session.add(verif)
        bill.bill_status = 'CANCELLED'
        db.session.commit()

        # Update lifecycle status
        status = bill.update_lifecycle_status()
        print(f"[OK] Post Cancellation Status: {status}")
        assert status == 'CANCELLED', f"Expected CANCELLED, got {status}"
        assert bill.is_verified is False, "Cancelled bill should not be considered verified"
        print("[OK] Verified property is_verified is False for Cancelled bill")

        # Test Dispatch Attempt via Flask test client
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['role_code'] = 'super_admin'

            response = client.post(f'/billing/bills/{bill.bill_id}/dispatch', data={
                'dispatch_date': '2026-09-14',
                'dispatch_mode': 'COURIER'
            }, follow_redirects=True)

            assert b"The bill has been CANCELLED" in response.data or b"must be VERIFIED" in response.data
            print("[OK] Dispatch Endpoint successfully blocked dispatch for CANCELLED bill!")

        # Clean up
        db.session.delete(bill)
        db.session.commit()

    print("==================================================")
    print("ALL BILL CANCELLATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()

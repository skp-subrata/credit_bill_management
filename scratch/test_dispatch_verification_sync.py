import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import app
from database import db
from models import Bill, BillVerification, BillDispatch, Patient, HospitalUnit, User

def run_tests():
    print("==================================================")
    print("Testing Dynamic Verification -> Dispatch Sync")
    print("==================================================")

    with app.app_context():
        unit = HospitalUnit.query.first()
        patient = Patient.query.first()
        user = User.query.first()

        if not unit or not patient or not user:
            print("Missing prerequisite unit/patient/user in DB.")
            return

        # Clean up existing test bill
        test_bill = Bill.query.filter_by(bill_number='BILL-TEST-SYNC-2902').first()
        if test_bill:
            db.session.delete(test_bill)
            db.session.commit()

        bill = Bill(
            bill_number='BILL-TEST-SYNC-2902',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-14',
            bill_amount=7500.0,
            approved_amount=7500.0,
            outstanding_amount=7500.0,
            created_by=user.id
        )
        db.session.add(bill)
        db.session.commit()

        # Step 1: Initial State -> VERIFICATION_PENDING
        assert bill.effective_dispatch_status == 'VERIFICATION_PENDING'
        print("[OK] Step 1 Initial Dispatch Status: VERIFICATION_PENDING")

        # Step 2: Approve & Verify -> READY_FOR_DISPATCH
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = user.id
                sess['role_code'] = 'super_admin'

            client.post(f'/billing/bills/{bill.bill_id}/verify', data={
                'action': 'VERIFY',
                'remarks': 'All items verified against discharge summary'
            }, follow_redirects=True)

            bill_obj = Bill.query.get(bill.bill_id)
            assert bill_obj.effective_dispatch_status == 'READY_FOR_DISPATCH'
            print("[OK] Step 2 Post-VERIFY Dispatch Status: READY_FOR_DISPATCH")

            # Dispatch entry
            client.post(f'/billing/bills/{bill.bill_id}/dispatch', data={
                'dispatch_date': '2026-09-14',
                'dispatch_mode': 'COURIER',
                'courier_name': 'DHL',
                'tracking_number': 'TRK-2902-SYNC'
            }, follow_redirects=True)

            bill_obj = Bill.query.get(bill.bill_id)
            assert bill_obj.effective_dispatch_status == 'DISPATCHED'
            print("[OK] Step 3 Post-DISPATCH Dispatch Status: DISPATCHED")

            # Step 4: Auditor updates verification to REJECT -> Dispatch Tracker updates to REJECTED
            client.post(f'/billing/bills/{bill.bill_id}/verify', data={
                'action': 'REJECT',
                'remarks': 'Audit query raised post-dispatch, items discrepancy'
            }, follow_redirects=True)

            bill_obj = Bill.query.get(bill.bill_id)
            assert bill_obj.effective_dispatch_status == 'REJECTED'
            assert bill_obj.dispatches[0].dispatch_status == 'REJECTED'
            print("[OK] Step 4 Post-REJECT Dispatch Status: REJECTED (Dispatches updated!)")

            # Step 5: Auditor updates verification to CANCEL -> Dispatch Tracker updates to CANCELLED
            client.post(f'/billing/bills/{bill.bill_id}/verify', data={
                'action': 'CANCEL',
                'remarks': 'Bill cancelled after audit'
            }, follow_redirects=True)

            bill_obj = Bill.query.get(bill.bill_id)
            assert bill_obj.effective_dispatch_status == 'CANCELLED'
            assert bill_obj.dispatches[0].dispatch_status == 'CANCELLED'
            print("[OK] Step 5 Post-CANCEL Dispatch Status: CANCELLED (Dispatches updated!)")

        # Clean up
        db.session.delete(bill_obj)
        db.session.commit()

    print("==================================================")
    print("ALL DISPATCH-VERIFICATION DYNAMIC SYNC TESTS PASSED!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()

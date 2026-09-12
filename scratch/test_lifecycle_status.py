import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app import app
from database import db
from models import Bill, BillVerification, BillDispatch, BillQuery, BillPayment, Patient, HospitalUnit, User

def run_tests():
    print("==================================================")
    print("Testing Billing Lifecycle Derived Status Logic")
    print("==================================================")

    with app.app_context():
        # Setup test bill
        unit = HospitalUnit.query.first()
        patient = Patient.query.first()
        user = User.query.first()

        if not unit or not patient or not user:
            print("Missing prerequisite unit/patient/user in DB.")
            return

        test_bill = Bill.query.filter_by(bill_number='BILL-TEST-LIFECYCLE').first()
        if test_bill:
            db.session.delete(test_bill)
            db.session.commit()

        bill = Bill(
            bill_number='BILL-TEST-LIFECYCLE',
            unit_id=unit.unit_id,
            patient_id=patient.patient_id,
            patient_name_snapshot=patient.patient_name,
            encounter_type='IP',
            bill_type='CREDIT',
            bill_date='2026-09-12',
            bill_amount=1000.0,
            approved_amount=1000.0,
            outstanding_amount=1000.0,
            created_by=user.id
        )
        db.session.add(bill)
        db.session.commit()

        # 1. Initial State: GENERATED
        status = bill.update_lifecycle_status()
        print(f"[Stage 1 - Initial] Status: '{status}' (Expected: 'GENERATED')")
        assert status == 'GENERATED', f"Expected GENERATED, got {status}"

        # 2. Verification Approved: VERIFIED
        verif1 = BillVerification(
            bill_id=bill.bill_id,
            verification_status='VERIFIED',
            verified_by=user.id,
            verification_remarks='Approved internal audit'
        )
        db.session.add(verif1)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 2 - Verification Approved] Status: '{status}' (Expected: 'VERIFIED')")
        assert status == 'VERIFIED', f"Expected VERIFIED, got {status}"

        # 3. Dispatch Recorded: DISPATCHED
        disp1 = BillDispatch(
            bill_id=bill.bill_id,
            bill_number=bill.bill_number,
            dispatch_date='2026-09-12',
            dispatch_mode='COURIER',
            courier_name='DHL',
            tracking_number='TRK-100200',
            dispatched_by=user.id
        )
        db.session.add(disp1)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 3 - Dispatch Recorded] Status: '{status}' (Expected: 'DISPATCHED')")
        assert status == 'DISPATCHED', f"Expected DISPATCHED, got {status}"

        # 4. Out-of-Sequence Activity: Re-verifying or logging verification note out of order
        print("\n--> Testing Out-of-Sequence Activity (Adding verification record after dispatch)...")
        verif2 = BillVerification(
            bill_id=bill.bill_id,
            verification_status='REJECTED', # out of sequence note/rework
            verified_by=user.id,
            verification_remarks='Out of sequence audit check'
        )
        db.session.add(verif2)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Out-of-Sequence Test] Status: '{status}' (Expected: 'DISPATCHED' - highest completed stage)")
        assert status == 'DISPATCHED', f"FAILED! Status downgraded to '{status}' instead of remaining 'DISPATCHED'!"

        # 5. Payer Query Raised: QUERIED
        query1 = BillQuery(
            bill_id=bill.bill_id,
            query_code=f"QRY-{bill.bill_number}-01",
            query_date='2026-09-12',
            query_description='Need itemized invoice',
            query_status='OPEN'
        )
        db.session.add(query1)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 4 - Query Raised] Status: '{status}' (Expected: 'QUERIED')")
        assert status == 'QUERIED', f"Expected QUERIED, got {status}"

        # 6. Payer Query Resolved: Back to DISPATCHED
        query1.query_status = 'RESOLVED'
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 4b - Query Resolved] Status: '{status}' (Expected: 'DISPATCHED')")
        assert status == 'DISPATCHED', f"Expected DISPATCHED, got {status}"

        # 7. Partial Payment Received: PARTIALLY_PAID
        pay1 = BillPayment(
            bill_id=bill.bill_id,
            payment_date='2026-09-12',
            utr_number='UTR-PARTIAL-101',
            amount_received=400.0,
            payment_status='PARTIAL',
            processed_by=user.id
        )
        bill.outstanding_amount = 600.0
        db.session.add(pay1)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 5 - Partial Payment] Status: '{status}' (Expected: 'PARTIALLY_PAID')")
        assert status == 'PARTIALLY_PAID', f"Expected PARTIALLY_PAID, got {status}"

        # 8. Full Payment Received: PAID
        pay2 = BillPayment(
            bill_id=bill.bill_id,
            payment_date='2026-09-12',
            utr_number='UTR-FULL-102',
            amount_received=600.0,
            payment_status='FULL',
            processed_by=user.id
        )
        bill.outstanding_amount = 0.0
        db.session.add(pay2)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 6 - Full Payment] Status: '{status}' (Expected: 'PAID')")
        assert status == 'PAID', f"Expected PAID, got {status}"

        # 9. Out-of-Sequence Activity on Paid Bill
        print("\n--> Testing Out-of-Sequence Activity on PAID Bill (Adding dispatch record)...")
        disp2 = BillDispatch(
            bill_id=bill.bill_id,
            bill_number=bill.bill_number,
            dispatch_date='2026-09-12',
            dispatch_mode='EMAIL',
            dispatched_by=user.id
        )
        db.session.add(disp2)
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Out-of-Sequence Test] Status: '{status}' (Expected: 'PAID')")
        assert status == 'PAID', f"FAILED! Status changed to '{status}' instead of remaining 'PAID'!"

        # 10. Closure: CLOSED
        bill.bill_status = 'CLOSED'
        db.session.commit()
        status = bill.update_lifecycle_status()
        print(f"[Stage 7 - Closure] Status: '{status}' (Expected: 'CLOSED')")
        assert status == 'CLOSED', f"Expected CLOSED, got {status}"

        # Clean up test bill
        db.session.delete(bill)
        db.session.commit()

    print("\n==================================================")
    print("ALL BILLING LIFECYCLE DERIVED STATUS TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()


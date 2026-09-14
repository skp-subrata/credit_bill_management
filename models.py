from datetime import datetime
from database import db

# Role Permission Association Table
class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_code = db.Column(db.String(50), unique=True, nullable=False)
    role_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), default='')

    users = db.relationship('User', backref='role', lazy=True)
    permissions = db.relationship('Permission', secondary='role_permissions', backref='roles')

class Permission(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    perm_code = db.Column(db.String(100), unique=True, nullable=False)
    perm_name = db.Column(db.String(150), nullable=False)
    module = db.Column(db.String(100), nullable=False)

class HospitalUnit(db.Model):
    __tablename__ = 'hospital_units'
    unit_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    hospital_name = db.Column(db.String(200), nullable=False)
    address_line1 = db.Column(db.String(255), default='')
    address_line2 = db.Column(db.String(255), default='')
    city = db.Column(db.String(100), default='')
    state = db.Column(db.String(100), default='')
    pincode = db.Column(db.String(20), default='')
    contact_no = db.Column(db.String(50), default='')
    email = db.Column(db.String(100), default='')
    status = db.Column(db.String(20), default='ACTIVE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = db.relationship('User', backref='hospital_unit', lazy=True)
    hospital_payers = db.relationship('HospitalPayer', backref='hospital_unit', lazy=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(50), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    hospital_unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=True)
    status = db.Column(db.String(20), default='ACTIVE')
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100), nullable=True)
    old_values = db.Column(db.Text, nullable=True)
    new_values = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), default='')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='audit_logs')

class Patient(db.Model):
    __tablename__ = 'patients'
    patient_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uhid = db.Column(db.String(50), unique=True, nullable=False, index=True)
    patient_name = db.Column(db.String(150), nullable=False)
    date_of_birth = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), default='OTHER')
    phone = db.Column(db.String(50), default='')
    email = db.Column(db.String(100), default='')
    address = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ip_admissions = db.relationship('IPAdmission', backref='patient', lazy=True)
    op_episodes = db.relationship('OPEpisode', backref='patient', lazy=True)
    bills = db.relationship('Bill', backref='patient', lazy=True)

class Payer(db.Model):
    __tablename__ = 'payers'
    payer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payer_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    payer_name = db.Column(db.String(200), nullable=False)
    payer_type = db.Column(db.String(50), nullable=False) # INSURANCE, CORPORATE, GOVERNMENT, TPA, PSU, OTHER
    contact_person = db.Column(db.String(150), default='')
    email = db.Column(db.String(100), default='')
    phone = db.Column(db.String(50), default='')
    address = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='ACTIVE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital_payers = db.relationship('HospitalPayer', backref='payer', lazy=True)

class HospitalPayer(db.Model):
    __tablename__ = 'hospital_payers'
    hospital_payer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=False, index=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('payers.payer_id'), nullable=False, index=True)
    payer_code_at_unit = db.Column(db.String(50), default='')
    billing_type = db.Column(db.String(50), default='CREDIT')
    credit_allowed = db.Column(db.Boolean, default=True)
    submission_tat_days = db.Column(db.Integer, default=15)
    monthly_submission = db.Column(db.Boolean, default=False)
    document_requirement = db.Column(db.Text, default='')
    approval_required = db.Column(db.Boolean, default=True)
    dispatch_mode = db.Column(db.String(50), default='COURIER')
    contact_email = db.Column(db.String(100), default='')
    contact_person = db.Column(db.String(150), default='')
    status = db.Column(db.String(20), default='ACTIVE')
    effective_from = db.Column(db.String(20), nullable=True)
    effective_to = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('unit_id', 'payer_id', name='_unit_payer_uc'),)

class IPAdmission(db.Model):
    __tablename__ = 'ip_admissions'
    admission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False, index=True)
    patient_name_snapshot = db.Column(db.String(150), nullable=False)
    admission_date = db.Column(db.String(20), nullable=False)
    admission_time = db.Column(db.String(20), default='')
    department = db.Column(db.String(100), default='General')
    doctor_name = db.Column(db.String(150), default='')
    hospital_payer_id = db.Column(db.Integer, db.ForeignKey('hospital_payers.hospital_payer_id'), nullable=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('payers.payer_id'), nullable=True)
    admission_status = db.Column(db.String(50), default='ADMITTED') # ADMITTED, DISCHARGE_INITIATED, DISCHARGED
    bill_type = db.Column(db.String(20), default='CREDIT') # CREDIT, CASH
    discharge_status = db.Column(db.String(50), default='NOT_DISCHARGED')
    billing_eligible = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = db.relationship('HospitalUnit', backref='ip_admissions')
    hospital_payer = db.relationship('HospitalPayer', backref='ip_admissions')
    payer = db.relationship('Payer', backref='ip_admissions')
    discharge = db.relationship('IPDischarge', backref='admission', uselist=False)

class IPDischarge(db.Model):
    __tablename__ = 'ip_discharges'
    discharge_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('ip_admissions.admission_id'), nullable=False, unique=True)
    ip_number = db.Column(db.String(50), nullable=False)
    discharge_date = db.Column(db.String(20), nullable=False)
    discharge_time = db.Column(db.String(20), default='')
    discharge_type = db.Column(db.String(50), default='REGULAR') # REGULAR, LAMA, ABSCONDED, EXPIRED, TRANSFER
    discharge_status = db.Column(db.String(50), default='COMPLETED')
    discharge_summary_status = db.Column(db.String(50), default='COMPLETED')
    final_bill_status = db.Column(db.String(50), default='PENDING')
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OPEpisode(db.Model):
    __tablename__ = 'op_episodes'
    episode_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    op_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False, index=True)
    patient_name_snapshot = db.Column(db.String(150), nullable=False)
    visit_date = db.Column(db.String(20), nullable=False)
    doctor_name = db.Column(db.String(150), default='')
    department = db.Column(db.String(100), default='Outpatient')
    payer_id = db.Column(db.Integer, db.ForeignKey('payers.payer_id'), nullable=True)
    hospital_payer_id = db.Column(db.Integer, db.ForeignKey('hospital_payers.hospital_payer_id'), nullable=True)
    episode_status = db.Column(db.String(50), default='ACTIVE')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = db.relationship('HospitalUnit', backref='op_episodes')
    payer = db.relationship('Payer', backref='op_episodes')

class Bill(db.Model):
    __tablename__ = 'bills'
    bill_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_number = db.Column(db.String(50), unique=False, nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False, index=True)
    patient_name_snapshot = db.Column(db.String(150), nullable=False)
    bill_type = db.Column(db.String(20), default='CREDIT') # CREDIT, CASH
    encounter_type = db.Column(db.String(20), nullable=False) # IP, OP
    ip_number = db.Column(db.String(50), nullable=True)
    episode_id = db.Column(db.Integer, db.ForeignKey('op_episodes.episode_id'), nullable=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('ip_admissions.admission_id'), nullable=True)
    discharge_id = db.Column(db.Integer, db.ForeignKey('ip_discharges.discharge_id'), nullable=True)
    payer_id = db.Column(db.Integer, db.ForeignKey('payers.payer_id'), nullable=True, index=True)
    hospital_payer_id = db.Column(db.Integer, db.ForeignKey('hospital_payers.hospital_payer_id'), nullable=True, index=True)
    bill_date = db.Column(db.String(20), nullable=False, index=True)
    bill_amount = db.Column(db.Float, nullable=False, default=0.0)
    approved_amount = db.Column(db.Float, default=0.0)
    outstanding_amount = db.Column(db.Float, nullable=False, default=0.0)
    bill_status = db.Column(db.String(50), default='GENERATED', index=True) 

    # Focused Delay Tracking Fields (Dispatch & Query Resolution)
    dispatch_sla_due_date = db.Column(db.String(20), nullable=True)
    dispatch_delay_days = db.Column(db.Integer, default=0)
    dispatch_delay_flag = db.Column(db.Boolean, default=False)
    dispatch_delayed_completed = db.Column(db.Boolean, default=False)
    dispatch_delay_status = db.Column(db.String(50), default='PENDING', index=True)

    query_sla_due_date = db.Column(db.String(20), nullable=True)
    query_delay_days = db.Column(db.Integer, default=0)
    query_delay_flag = db.Column(db.Boolean, default=False)
    query_delayed_completed = db.Column(db.Boolean, default=False)
    query_delay_status = db.Column(db.String(50), default='NOT_APPLICABLE', index=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unit = db.relationship('HospitalUnit', backref='bills')
    payer = db.relationship('Payer', backref='bills')
    hospital_payer = db.relationship('HospitalPayer', backref='bills')
    creator = db.relationship('User', foreign_keys=[created_by])

    verifications = db.relationship('BillVerification', backref='bill', lazy=True, cascade='all, delete-orphan')
    dispatches = db.relationship('BillDispatch', backref='bill', lazy=True, cascade='all, delete-orphan')
    queries = db.relationship('BillQuery', backref='bill', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('BillPayment', backref='bill', lazy=True, cascade='all, delete-orphan')

    def calculate_lifecycle_status(self):
        """
        Derives the Bill Status from the defined Billing Lifecycle stage hierarchy,
        rather than relying on out-of-sequence activity logs.

        Hierarchy of Lifecycle Stages (Lowest to Highest):
        1. GENERATED (Base stage when bill is created)
        2. VERIFICATION_PENDING / VERIFIED (Internal audit stage)
        3. DISPATCHED (Payer submission completed)
        4. QUERIED (Active open query with Payer)
        5. PARTIALLY_PAID (Partial settlement received)
        6. PAID (Full payment settled)
        7. CLOSED (Formally closed/archived)
        """
        if self.bill_status == 'CLOSED':
            return 'CLOSED'

        # Stage 6: PAID (full settlement)
        if self.payments and len(self.payments) > 0 and self.outstanding_amount <= 0:
            return 'PAID'

        # Stage 5: PARTIALLY_PAID (partial settlement)
        if self.payments and len(self.payments) > 0 and self.outstanding_amount < self.bill_amount:
            return 'PARTIALLY_PAID'

        # Stage 4: QUERIED (active open query with payer)
        has_open_query = any(q.query_status in ('OPEN', 'PENDING') for q in (self.queries or []))
        if has_open_query:
            return 'QUERIED'

        # Stage 3: DISPATCHED (submitted to payer)
        if self.dispatches and len(self.dispatches) > 0:
            return 'DISPATCHED'

        # Stage 2: VERIFIED (internal audit approved)
        has_approved_verification = any(v.verification_status == 'VERIFIED' for v in (self.verifications or []))
        if has_approved_verification:
            return 'VERIFIED'

        has_rejected_verification = any(v.verification_status == 'REJECTED' for v in (self.verifications or []))
        if has_rejected_verification:
            return 'VERIFICATION_PENDING'

        return 'GENERATED'

    @property
    def is_verified(self):
        """Returns True if the bill has been verified or is at/past the VERIFIED lifecycle stage."""
        if any(v.verification_status == 'VERIFIED' for v in (self.verifications or [])):
            return True
        return self.bill_status in ('VERIFIED', 'DISPATCHED', 'QUERIED', 'PARTIALLY_PAID', 'PAID', 'CLOSED')

    def update_lifecycle_status(self):
        """Updates and persists self.bill_status and delay metrics based on the highest completed lifecycle stage and SLA due dates."""
        self.bill_status = self.calculate_lifecycle_status()
        try:
            from utils.tat import calculate_bill_delay_metrics
            calculate_bill_delay_metrics(self)
        except Exception:
            pass
        return self.bill_status

class BillVerification(db.Model):
    __tablename__ = 'bill_verifications'
    verification_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.bill_id'), nullable=False)
    verification_status = db.Column(db.String(50), default='PENDING')
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow)
    verification_remarks = db.Column(db.Text, default='')
    rejection_reason = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    verifier = db.relationship('User', foreign_keys=[verified_by])

class BillDispatch(db.Model):
    __tablename__ = 'bill_dispatch'
    dispatch_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.bill_id'), nullable=False)
    bill_number = db.Column(db.String(50), nullable=False)
    dispatch_date = db.Column(db.String(20), nullable=False)
    dispatch_mode = db.Column(db.String(50), default='COURIER')
    courier_name = db.Column(db.String(100), default='')
    tracking_number = db.Column(db.String(100), default='')
    recipient_name = db.Column(db.String(150), default='')
    recipient_email = db.Column(db.String(100), default='')
    dispatch_status = db.Column(db.String(50), default='DISPATCHED', index=True)
    dispatched_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    acknowledgement_date = db.Column(db.String(20), nullable=True)
    acknowledgement_by = db.Column(db.String(150), default='')
    acknowledgement_status = db.Column(db.String(50), default='PENDING')
    remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    dispatcher = db.relationship('User', foreign_keys=[dispatched_by])

class BillQuery(db.Model):
    __tablename__ = 'bill_queries'
    query_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.bill_id'), nullable=False)
    query_code = db.Column(db.String(50), unique=True, nullable=False)
    query_date = db.Column(db.String(20), nullable=False)
    query_type = db.Column(db.String(100), default='DOCUMENTATION')
    query_description = db.Column(db.Text, nullable=False)
    raised_by_payer = db.Column(db.String(150), default='')
    query_status = db.Column(db.String(50), default='OPEN', index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    due_date = db.Column(db.String(20), nullable=True)
    response_remarks = db.Column(db.Text, default='')
    responded_at = db.Column(db.DateTime, nullable=True)
    responded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignee = db.relationship('User', foreign_keys=[assigned_to])
    responder = db.relationship('User', foreign_keys=[responded_by])

class BillPayment(db.Model):
    __tablename__ = 'bill_payments'
    payment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bills.bill_id'), nullable=False)
    payment_date = db.Column(db.String(20), nullable=False)
    payment_mode = db.Column(db.String(50), default='NEFT/RTGS')
    utr_number = db.Column(db.String(100), nullable=False)
    amount_received = db.Column(db.Float, nullable=False, default=0.0)
    short_fall_amount = db.Column(db.Float, default=0.0)
    disallowance_reason = db.Column(db.Text, default='')
    payment_status = db.Column(db.String(50), default='FULL')
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    processor = db.relationship('User', foreign_keys=[processed_by])


# ============================================================
# HIS DATA IMPORT & SYNCHRONIZATION EXTENSION MODELS
# ============================================================

class SyncBatch(db.Model):
    __tablename__ = 'sync_batches'
    batch_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_system = db.Column(db.String(50), default='HIS_EXCEL') # HIS_EXCEL, OUTLOOK_EMAIL, HIS_API, SFTP
    source_type = db.Column(db.String(50), default='FILE_UPLOAD') # FILE_UPLOAD, EMAIL_ATTACHMENT, API_FEED
    source_file_name = db.Column(db.String(255), nullable=False)
    source_file_hash = db.Column(db.String(64), index=True, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    total_records = db.Column(db.Integer, default=0)
    new_records = db.Column(db.Integer, default=0)
    updated_records = db.Column(db.Integer, default=0)
    unchanged_records = db.Column(db.Integer, default=0)
    duplicate_records = db.Column(db.Integer, default=0)
    invalid_records = db.Column(db.Integer, default=0)
    mapping_pending_records = db.Column(db.Integer, default=0)
    failed_records = db.Column(db.Integer, default=0)
    successful_records = db.Column(db.Integer, default=0)
    batch_status = db.Column(db.String(50), default='UPLOADED', index=True) 
    # UPLOADED, VALIDATING, VALIDATED, PROCESSING, COMPLETED, PARTIALLY_COMPLETED, FAILED, CANCELLED
    remarks = db.Column(db.Text, default='')

    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    staging_rows = db.relationship('HISIPStaging', backref='batch', lazy=True, cascade='all, delete-orphan')

class HISIPStaging(db.Model):
    __tablename__ = 'his_ip_staging'
    staging_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('sync_batches.batch_id'), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=False)

    # 36 Raw HIS Fields
    uhid = db.Column(db.String(100), index=True)
    patientname = db.Column(db.String(200))
    ipnumber = db.Column(db.String(100), index=True)
    gender = db.Column(db.String(50))
    age = db.Column(db.String(50))
    admitteddate = db.Column(db.String(100))
    planingdate = db.Column(db.String(100))
    closingdate = db.Column(db.String(100))
    primarydoctor = db.Column(db.String(200))
    nursecheckedouttime = db.Column(db.String(100))
    admiting_doctor = db.Column(db.String(200))
    admiting_doctor_dept = db.Column(db.String(200))
    treating_doctor = db.Column(db.String(200))
    treating_doctor_dept = db.Column(db.String(200))
    interimdate = db.Column(db.String(100))
    discharge_billdate = db.Column(db.String(100))
    bed_occupied = db.Column(db.String(100))
    specialization = db.Column(db.String(200))
    specializationdesc = db.Column(db.String(200))
    bedno = db.Column(db.String(100))
    bedtype = db.Column(db.String(100))
    billablebed = db.Column(db.String(100))
    bednumber = db.Column(db.String(100))
    wardname = db.Column(db.String(200))
    companyname = db.Column(db.String(200))
    refraldoctor = db.Column(db.String(200))
    currentstatus = db.Column(db.String(100))
    reasonandremarks = db.Column(db.Text)
    contactno = db.Column(db.String(100))
    address1 = db.Column(db.Text)
    countryname = db.Column(db.String(100))
    statename = db.Column(db.String(100))
    cityname = db.Column(db.String(100))
    districtname = db.Column(db.String(100))
    createdby = db.Column(db.String(100))
    locationid = db.Column(db.String(100), index=True)

    raw_payload = db.Column(db.Text, nullable=True) # Full JSON copy
    validation_status = db.Column(db.String(50), default='PENDING', index=True) # VALID, INVALID, WARNING, MAPPING_PENDING
    validation_error = db.Column(db.Text, default='')
    processing_status = db.Column(db.String(50), default='PENDING', index=True) # PENDING, PROCESSED, SKIPPED, FAILED
    classification = db.Column(db.String(50), default='NEW') # NEW, UPDATED, UNCHANGED, DUPLICATE, INVALID, MAPPING_PENDING
    application_record_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

class HISPayerMapping(db.Model):
    __tablename__ = 'his_payer_mapping'
    mapping_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_company_name = db.Column(db.String(200), index=True, nullable=False)
    normalized_company_name = db.Column(db.String(200), index=True, nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey('payers.payer_id'), nullable=True)
    payer_type = db.Column(db.String(50), default='INSURANCE')
    bill_type = db.Column(db.String(20), default='CREDIT') # CREDIT, CASH
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payer = db.relationship('Payer', foreign_keys=[payer_id])
    unit = db.relationship('HospitalUnit', foreign_keys=[unit_id])

class DoctorMaster(db.Model):
    __tablename__ = 'doctor_master'
    doctor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_code = db.Column(db.String(50), unique=True, nullable=False)
    doctor_name = db.Column(db.String(200), nullable=False)
    normalized_doctor_name = db.Column(db.String(200), index=True, nullable=False)
    department = db.Column(db.String(100), default='')
    specialization = db.Column(db.String(100), default='')
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HISDoctorMapping(db.Model):
    __tablename__ = 'his_doctor_mapping'
    mapping_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_doctor_name = db.Column(db.String(200), index=True, nullable=False)
    normalized_doctor_name = db.Column(db.String(200), index=True, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor_master.doctor_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    doctor = db.relationship('DoctorMaster', foreign_keys=[doctor_id])

class HISSyncSettings(db.Model):
    __tablename__ = 'his_sync_settings'
    setting_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('hospital_units.unit_id'), nullable=True)
    sync_mode = db.Column(db.String(50), default='INCREMENTAL_SYNC') # FULL_SYNC, INCREMENTAL_SYNC
    auto_sync_enabled = db.Column(db.Boolean, default=False)
    schedule_frequency = db.Column(db.String(50), default='HOURLY')
    email_ingestion_enabled = db.Column(db.Boolean, default=False)
    email_folder = db.Column(db.String(100), default='Inbox/HIS')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailIngestionLog(db.Model):
    __tablename__ = 'email_ingestion_logs'
    email_log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    external_message_id = db.Column(db.String(255), unique=True, nullable=False)
    sender = db.Column(db.String(200), nullable=False)
    recipient = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(255), default='')
    received_date = db.Column(db.DateTime, nullable=False)
    attachment_name = db.Column(db.String(255), default='')
    processing_status = db.Column(db.String(50), default='PROCESSED')
    batch_id = db.Column(db.Integer, db.ForeignKey('sync_batches.batch_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminUploadHistory(db.Model):
    __tablename__ = 'admin_upload_history'
    history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    data_category = db.Column(db.String(100), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    total_records = db.Column(db.Integer, default=0)
    success_records = db.Column(db.Integer, default=0)
    failed_records = db.Column(db.Integer, default=0)
    duplicate_records = db.Column(db.Integer, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    error_summary_json = db.Column(db.Text, default='[]')

    uploader = db.relationship('User', foreign_keys=[uploaded_by])


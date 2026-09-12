from datetime import datetime, timedelta

def parse_date_safe(date_str):
    """Parse string date in YYYY-MM-DD or DD-MM-YYYY or DD.MM.YYYY format."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str[:10], fmt)
        except Exception:
            pass
    return None

def calculate_tat_start_date(bill_date_input, monthly_submission=False):
    """
    Calculate TAT Start Date based on Monthly Submission flag.
    
    Rule:
    - If Monthly Submission = False (or No):
      TAT Start Date = Bill Build Date.
      
    - If Monthly Submission = True (or Yes):
      All discharges/builds generated during a month become eligible for submission
      in the following month, and TAT starts from 1st day of the following month.
    """
    bdate = parse_date_safe(bill_date_input) if isinstance(bill_date_input, str) else bill_date_input
    if not bdate:
        return datetime.now()

    if not monthly_submission:
        return bdate

    # Monthly submission = True: 1st day of the following month
    if bdate.month == 12:
        return datetime(bdate.year + 1, 1, 1)
    else:
        return datetime(bdate.year, bdate.month + 1, 1)

def calculate_tat_metrics(bill_date_input, submission_tat_days=15, monthly_submission=False, current_date=None):
    """
    Calculate comprehensive TAT SLA metrics including TAT Start Date, TAT Due Date, Days Remaining, and Status.
    """
    if current_date is None:
        current_date = datetime.now()

    bdate = parse_date_safe(bill_date_input) if isinstance(bill_date_input, str) else bill_date_input
    if not bdate:
        bdate = current_date

    tat_start = calculate_tat_start_date(bdate, monthly_submission)
    tat_due = tat_start + timedelta(days=int(submission_tat_days or 15))

    days_remaining = (tat_due.date() - current_date.date()).days

    if days_remaining < 0:
        sla_status = 'BREACHED'
    elif days_remaining <= 3:
        sla_status = 'DUE_SOON'
    else:
        sla_status = 'ON_TIME'

    return {
        "build_date": bdate.strftime('%Y-%m-%d'),
        "monthly_submission": bool(monthly_submission),
        "tat_start_date": tat_start.strftime('%Y-%m-%d'),
        "tat_due_date": tat_due.strftime('%Y-%m-%d'),
        "submission_tat_days": int(submission_tat_days or 15),
        "days_remaining": days_remaining,
        "sla_status": sla_status
    }

def get_dispatch_date_bounds(ref_date=None):
    """
    Returns (min_date_str, max_date_str) in YYYY-MM-DD format.
    Rule: Minimum Dispatch Date = Today - 3 days, Maximum Dispatch Date = Today.
    """
    if ref_date is None:
        ref_d = datetime.now().date()
    elif isinstance(ref_date, datetime):
        ref_d = ref_date.date()
    else:
        ref_d = ref_date
        
    min_d = ref_d - timedelta(days=3)
    max_d = ref_d
    return min_d.strftime('%Y-%m-%d'), max_d.strftime('%Y-%m-%d')

def validate_dispatch_date(dispatch_date_input, ref_date=None):
    """
    Validates if dispatch_date is within [Today - 3 days, Today].
    Returns (is_valid, error_message).
    """
    if not dispatch_date_input:
        return False, "Dispatch Date is required."
        
    d_obj = parse_date_safe(dispatch_date_input)
    if not d_obj:
        return False, f"Invalid date format for Dispatch Date: '{dispatch_date_input}'."
        
    dispatch_d = d_obj.date()
    
    if ref_date is None:
        ref_d = datetime.now().date()
    elif isinstance(ref_date, datetime):
        ref_d = ref_date.date()
    else:
        ref_d = ref_date

    min_d = ref_d - timedelta(days=3)
    max_d = ref_d

    if dispatch_d < min_d:
        return False, f"Dispatch Date '{dispatch_d.strftime('%Y-%m-%d')}' is invalid. Minimum allowed date is '{min_d.strftime('%Y-%m-%d')}' (Today - 3 days)."
    if dispatch_d > max_d:
        return False, f"Dispatch Date '{dispatch_d.strftime('%Y-%m-%d')}' cannot be in the future. Maximum allowed date is '{max_d.strftime('%Y-%m-%d')}' (Today)."
        
    return True, None

def calculate_bill_delay_metrics(bill, current_date=None):
    """
    Evaluates Dispatch Delay and Query Resolution Delay metrics for a given Bill entity.
    Updates bill fields and returns a metric payload.
    
    Dispatch Delay Statuses:
    - PENDING / WITHIN_SLA (Green): Pending dispatch, currently within SLA
    - DELAYED (Red): SLA crossed and bill not yet dispatched
    - DISPATCHED_LATE (Red): Dispatched after SLA due date (Historical fact preserved)
    - ON_TIME (Green): Dispatched on or before SLA due date

    Query Resolution Delay Statuses:
    - NOT_APPLICABLE: No queries raised
    - PENDING / WITHIN_SLA: Active query within SLA
    - QUERY_DELAYED: Active query past SLA
    - QUERY_RESOLVED_LATE: Query resolved after SLA
    - ON_TIME: Query resolved on/before SLA
    """
    if current_date is None:
        current_d = datetime.now().date()
    elif isinstance(current_date, datetime):
        current_d = current_date.date()
    else:
        current_d = current_date

    tat_days = 15
    monthly_sub = False
    if hasattr(bill, 'hospital_payer') and bill.hospital_payer:
        tat_days = bill.hospital_payer.submission_tat_days or 15
        monthly_sub = bill.hospital_payer.monthly_submission

    tat_info = calculate_tat_metrics(bill.bill_date, submission_tat_days=tat_days, monthly_submission=monthly_sub, current_date=current_date)
    dispatch_due_str = tat_info["tat_due_date"]
    dispatch_due_d = parse_date_safe(dispatch_due_str).date()

    # --- 1. DISPATCH DELAY EVALUATION ---
    dispatch_delay_status = 'PENDING'
    dispatch_delay_days = 0
    dispatch_delay_flag = False
    dispatch_delayed_completed = False

    dispatches = getattr(bill, 'dispatches', []) or []
    if dispatches and len(dispatches) > 0:
        actual_disp_str = dispatches[0].dispatch_date
        actual_disp_d = parse_date_safe(actual_disp_str).date() if actual_disp_str else current_d
        
        if actual_disp_d > dispatch_due_d:
            dispatch_delay_days = (actual_disp_d - dispatch_due_d).days
            dispatch_delay_flag = True
            dispatch_delayed_completed = True
            dispatch_delay_status = 'DISPATCHED_LATE'
        else:
            dispatch_delay_days = 0
            dispatch_delay_flag = False
            dispatch_delayed_completed = False
            dispatch_delay_status = 'ON_TIME'
    else:
        if current_d > dispatch_due_d:
            dispatch_delay_days = (current_d - dispatch_due_d).days
            dispatch_delay_flag = True
            dispatch_delayed_completed = False
            dispatch_delay_status = 'DELAYED'
        else:
            dispatch_delay_days = 0
            dispatch_delay_flag = False
            dispatch_delayed_completed = False
            dispatch_delay_status = 'PENDING'

    # --- 2. QUERY RESOLUTION DELAY EVALUATION ---
    query_delay_status = 'NOT_APPLICABLE'
    query_delay_days = 0
    query_delay_flag = False
    query_delayed_completed = False
    query_due_str = None

    queries = getattr(bill, 'queries', []) or []
    if queries and len(queries) > 0:
        latest_q = queries[-1]
        q_due_d = parse_date_safe(latest_q.due_date).date() if latest_q.due_date else (parse_date_safe(latest_q.query_date).date() + timedelta(days=7))
        query_due_str = q_due_d.strftime('%Y-%m-%d')

        if latest_q.query_status in ('RESOLVED', 'CLOSED'):
            resp_d = latest_q.responded_at.date() if latest_q.responded_at else parse_date_safe(latest_q.query_date).date()
            if resp_d > q_due_d:
                query_delay_days = (resp_d - q_due_d).days
                query_delay_flag = True
                query_delayed_completed = True
                query_delay_status = 'QUERY_RESOLVED_LATE'
            else:
                query_delay_days = 0
                query_delay_flag = False
                query_delayed_completed = False
                query_delay_status = 'ON_TIME'
        else:
            if current_d > q_due_d:
                query_delay_days = (current_d - q_due_d).days
                query_delay_flag = True
                query_delayed_completed = False
                query_delay_status = 'QUERY_DELAYED'
            else:
                query_delay_days = 0
                query_delay_flag = False
                query_delayed_completed = False
                query_delay_status = 'PENDING'

    # Assign attributes to bill object
    bill.dispatch_sla_due_date = dispatch_due_str
    bill.dispatch_delay_days = dispatch_delay_days
    bill.dispatch_delay_flag = dispatch_delay_flag
    bill.dispatch_delayed_completed = dispatch_delayed_completed
    bill.dispatch_delay_status = dispatch_delay_status

    bill.query_sla_due_date = query_due_str
    bill.query_delay_days = query_delay_days
    bill.query_delay_flag = query_delay_flag
    bill.query_delayed_completed = query_delayed_completed
    bill.query_delay_status = query_delay_status

    return {
        "dispatch_sla_due_date": dispatch_due_str,
        "dispatch_delay_days": dispatch_delay_days,
        "dispatch_delay_flag": dispatch_delay_flag,
        "dispatch_delayed_completed": dispatch_delayed_completed,
        "dispatch_delay_status": dispatch_delay_status,
        "query_sla_due_date": query_due_str,
        "query_delay_days": query_delay_days,
        "query_delay_flag": query_delay_flag,
        "query_delayed_completed": query_delayed_completed,
        "query_delay_status": query_delay_status
    }




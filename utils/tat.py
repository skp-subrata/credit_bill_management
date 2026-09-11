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

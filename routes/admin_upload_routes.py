import json, io, csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify, Response
from database import db
from models import AdminUploadHistory, User
from utils.auth import login_required, permission_required
from utils.admin_upload_engine import (
    DATA_CATEGORIES_CONFIG, generate_template, validate_admin_upload, execute_admin_import,
    save_upload_stage, get_upload_stage, clear_upload_stage
)

admin_upload_bp = Blueprint('admin_upload', __name__, url_prefix='/admin/data-upload')

def check_admin_access():
    """Verify that current session user has Super Admin or Admin role."""
    role = session.get('role_code')
    return role in ('super_admin', 'admin')

# --- MAIN DASHBOARD VIEW ---
@admin_upload_bp.route('', methods=['GET'])
@login_required
def data_upload():
    if not check_admin_access():
        flash("Access Denied: Only Super Admin and Admin users can access Data Upload Module.", "error")
        return redirect(url_for('main.dashboard'))

    categories = [{'key': k, 'label': v['label']} for k, v in DATA_CATEGORIES_CONFIG.items()]
    history_logs = AdminUploadHistory.query.order_by(AdminUploadHistory.history_id.desc()).limit(50).all()
    user_id = session.get('user_id')
    active_category = session.get('admin_upload_category')

    preview_data = None
    if active_category:
        preview_data = get_upload_stage(user_id, active_category)

    return render_template(
        'admin/data_upload.html',
        categories=categories,
        history_logs=history_logs,
        preview_data=preview_data
    )

# --- DOWNLOAD TEMPLATE ---
@admin_upload_bp.route('/template/<category_key>', methods=['GET'])
@login_required
def download_template(category_key):
    if not check_admin_access():
        flash("Access Denied.", "error")
        return redirect(url_for('main.dashboard'))

    fmt = request.args.get('fmt', 'xlsx').lower()
    if fmt not in ('xlsx', 'csv'):
        fmt = 'xlsx'

    try:
        data_bytes, mimetype, filename = generate_template(category_key, fmt=fmt)
        return Response(
            data_bytes,
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        flash(f"Template generation error: {str(e)}", "error")
        return redirect(url_for('admin_upload.data_upload'))

# --- FILE VALIDATION & PREVIEW ---
@admin_upload_bp.route('/validate', methods=['POST'])
@login_required
def validate_file():
    if not check_admin_access():
        return jsonify({'error': 'Access Denied'}), 403

    category_key = request.form.get('data_category')
    file_storage = request.files.get('upload_file')

    if not category_key or not file_storage:
        flash("Please select a Data Category and choose a valid file.", "error")
        return redirect(url_for('admin_upload.data_upload'))

    report = validate_admin_upload(category_key, file_storage)
    
    if 'error' in report:
        flash(report['error'], "error")
        return redirect(url_for('admin_upload.data_upload'))

    user_id = session.get('user_id', 1)
    
    # Store validation state in server-side staging file
    save_upload_stage(user_id, category_key, report)
    session['admin_upload_category'] = category_key

    history_logs = AdminUploadHistory.query.order_by(AdminUploadHistory.history_id.desc()).limit(50).all()
    categories = [{'key': k, 'label': v['label']} for k, v in DATA_CATEGORIES_CONFIG.items()]

    return render_template(
        'admin/data_upload.html',
        categories=categories,
        history_logs=history_logs,
        preview_data=report
    )

# --- EXECUTE IMPORT ---
@admin_upload_bp.route('/import', methods=['POST'])
@login_required
def import_data():
    if not check_admin_access():
        flash("Access Denied.", "error")
        return redirect(url_for('main.dashboard'))

    user_id = session.get('user_id', 1)
    category_key = request.form.get('data_category') or session.get('admin_upload_category')

    if not category_key:
        flash("No active upload category specified.", "error")
        return redirect(url_for('admin_upload.data_upload'))

    preview = get_upload_stage(user_id, category_key)
    if not preview or not preview.get('valid_records'):
        flash("No validated preview data found to import.", "error")
        return redirect(url_for('admin_upload.data_upload'))

    valid_records = preview['valid_records']
    filename = preview['filename']

    result = execute_admin_import(category_key, valid_records, user_id, filename)

    # Clear server-side staging file and session state
    clear_upload_stage(user_id, category_key)
    session.pop('admin_upload_category', None)

    flash(f"Data Import Completed for '{preview.get('category_label', category_key)}'! Successfully imported {result['success_count']} record(s). (Failed: {result['failed_count']}).", "success")
    return redirect(url_for('admin_upload.data_upload'))

# --- CANCEL PREVIEW ---
@admin_upload_bp.route('/cancel-preview', methods=['POST'])
@login_required
def cancel_preview():
    user_id = session.get('user_id', 1)
    category_key = request.form.get('data_category') or session.get('admin_upload_category')
    if category_key:
        clear_upload_stage(user_id, category_key)
    session.pop('admin_upload_category', None)
    flash("Upload preview cancelled.", "warning")
    return redirect(url_for('admin_upload.data_upload'))

# --- DOWNLOAD ERROR REPORT ---
@admin_upload_bp.route('/history/<int:history_id>/errors', methods=['GET'])
@login_required
def download_errors(history_id):
    if not check_admin_access():
        flash("Access Denied.", "error")
        return redirect(url_for('main.dashboard'))

    history = AdminUploadHistory.query.get_or_404(history_id)
    error_list = json.loads(history.error_summary_json or '[]')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Row Number', 'Failure Reason'])
    for err in error_list:
        writer.writerow([err.get('row', 'N/A'), err.get('reason', '')])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=ErrorReport_UploadBatch_{history_id}.csv"}
    )


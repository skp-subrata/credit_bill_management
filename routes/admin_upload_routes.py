import json, io, csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify, Response
from database import db
from models import AdminUploadHistory, User
from utils.auth import login_required, permission_required
from utils.admin_upload_engine import (
    DATA_CATEGORIES_CONFIG, generate_template, validate_admin_upload, execute_admin_import
)

admin_upload_bp = Blueprint('admin_upload', __name__, url_prefix='/admin/data-upload')

def check_admin_access():
    """Verify that current session user has Super Admin or Admin role."""
    role = session.get('role_code')
    return role in ('super_admin', 'admin')

# --- DATA UPLOAD MAIN SCREEN ---
@admin_upload_bp.route('', methods=['GET'])
@login_required
def data_upload():
    if not check_admin_access():
        flash("Access Denied: Admin or Super Admin permissions required for Data Upload.", "error")
        return redirect(url_for('main.dashboard'))

    history_logs = AdminUploadHistory.query.order_by(AdminUploadHistory.history_id.desc()).limit(50).all()
    
    categories = [
        {'key': k, 'label': v['label']}
        for k, v in DATA_CATEGORIES_CONFIG.items()
    ]

    return render_template('admin/data_upload.html', categories=categories, history_logs=history_logs)

# --- DYNAMIC TEMPLATE DOWNLOAD ---
@admin_upload_bp.route('/template/<category_key>/<fmt>', methods=['GET'])
@login_required
def download_template(category_key, fmt):
    if not check_admin_access():
        flash("Access Denied.", "error")
        return redirect(url_for('main.dashboard'))

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

    # Store validation state in session temporarily for import execution
    session['admin_upload_preview'] = {
        'data_category': category_key,
        'filename': file_storage.filename,
        'valid_records': report['valid_records'],
        'total_count': report['total_records'],
        'valid_count': report['valid_count'],
        'error_count': report['error_count'],
        'duplicate_count': report['duplicate_count'],
        'errors': report['errors']
    }

    history_logs = AdminUploadHistory.query.order_by(AdminUploadHistory.history_id.desc()).limit(50).all()
    categories = [{'key': k, 'label': v['label']} for k, v in DATA_CATEGORIES_CONFIG.items()]

    return render_template(
        'admin/data_upload.html',
        categories=categories,
        history_logs=history_logs,
        preview_data=session['admin_upload_preview']
    )

# --- EXECUTE IMPORT ---
@admin_upload_bp.route('/import', methods=['POST'])
@login_required
def import_data():
    if not check_admin_access():
        flash("Access Denied.", "error")
        return redirect(url_for('main.dashboard'))

    preview = session.get('admin_upload_preview')
    if not preview or not preview.get('valid_records'):
        flash("No validated preview data found to import.", "error")
        return redirect(url_for('admin_upload.data_upload'))

    category_key = preview['data_category']
    valid_records = preview['valid_records']
    filename = preview['filename']
    user_id = session.get('user_id')

    result = execute_admin_import(category_key, valid_records, user_id, filename)

    # Clear preview session
    session.pop('admin_upload_preview', None)

    flash(f"Data Import Completed for '{category_key}'! Successfully imported {result['success_count']} record(s). (Failed: {result['failed_count']}).", "success")
    return redirect(url_for('admin_upload.data_upload'))

# --- CANCEL PREVIEW ---
@admin_upload_bp.route('/cancel-preview', methods=['POST'])
@login_required
def cancel_preview():
    session.pop('admin_upload_preview', None)
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


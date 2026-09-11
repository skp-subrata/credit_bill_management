import os
from flask import Flask, render_template, request, session, redirect, url_for
from config import Config
from database import db
from models import HospitalUnit, User

# Import Blueprints
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.user_routes import user_bp
from routes.master_routes import master_bp
from routes.encounter_routes import encounter_bp
from routes.billing_routes import billing_bp
from routes.report_routes import report_bp
from routes.his_sync_routes import his_sync_bp

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(user_bp)
app.register_blueprint(master_bp)
app.register_blueprint(encounter_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(report_bp)
app.register_blueprint(his_sync_bp)

# Context Processor for Templates
@app.context_processor
def inject_global_context():
    active_unit_id = session.get('active_unit_id')
    current_unit = None
    all_units = []
    
    if session.get('user_id'):
        try:
            all_units = HospitalUnit.query.filter_by(status='ACTIVE').all()
            if active_unit_id:
                current_unit = HospitalUnit.query.get(active_unit_id)
            if not current_unit and all_units:
                current_unit = all_units[0]
                session['active_unit_id'] = current_unit.unit_id
        except Exception:
            pass

    return dict(
        current_unit=current_unit,
        all_active_units=all_units,
        request_endpoint=request.endpoint or ''
    )

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html'), 500

# Create Tables & Apply Schema Adjustments within Context
with app.app_context():
    db.create_all()
    try:
        with db.engine.connect() as conn:
            # Check ip_admissions
            col_rows = conn.execute(db.text("PRAGMA table_info(ip_admissions)")).fetchall()
            columns = [r[1] for r in col_rows] if col_rows else []
            if columns and 'billing_eligible' not in columns:
                conn.execute(db.text("ALTER TABLE ip_admissions ADD COLUMN billing_eligible BOOLEAN DEFAULT 0"))
                conn.commit()

            # Check hospital_payers
            hp_col_rows = conn.execute(db.text("PRAGMA table_info(hospital_payers)")).fetchall()
            hp_columns = [r[1] for r in hp_col_rows] if hp_col_rows else []
            if hp_columns and 'monthly_submission' not in hp_columns:
                conn.execute(db.text("ALTER TABLE hospital_payers ADD COLUMN monthly_submission BOOLEAN DEFAULT 0"))
                conn.commit()
    except Exception:
        pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

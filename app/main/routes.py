from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from app.models import CertificateVerification

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin_or_staff:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/verify', methods=['GET', 'POST'])
def verify_search():
    if request.method == 'POST':
        cert_id = request.form.get('certificate_id', '').strip()
        if cert_id:
            return redirect(url_for('main.verify_certificate', certificate_id=cert_id))
        flash('Please enter a valid Certificate Identification Number.', 'warning')
    return render_template('public/verify_search.html')

@main_bp.route('/verify/<certificate_id>')
def verify_certificate(certificate_id):
    cert = CertificateVerification.query.filter_by(certificate_no=certificate_id.strip()).first()
    return render_template('public/verify_result.html', cert=cert, cert_id=certificate_id)

from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import InternshipPlan, CertificateVerification

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    plan_1m = InternshipPlan.query.filter_by(plan_code='1_MONTH_PROJECT').first()
    plan_3m = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()
    return render_template('public/index.html', plan_1m=plan_1m, plan_3m=plan_3m)

@main_bp.route('/internships')
def internships():
    plans = InternshipPlan.query.filter_by(is_active=True).order_by(InternshipPlan.duration_months.asc()).all()
    return render_template('public/internships.html', plans=plans)

@main_bp.route('/internships/1-month')
def internship_1month():
    plan = InternshipPlan.query.filter_by(plan_code='1_MONTH_PROJECT').first()
    return render_template('public/internship_1month.html', plan=plan)

@main_bp.route('/internships/3-month')
def internship_3month():
    plan = InternshipPlan.query.filter_by(plan_code='3_MONTH_PROFESSIONAL').first()
    return render_template('public/internship_3month.html', plan=plan)

@main_bp.route('/about')
def about():
    return render_template('public/about.html')

@main_bp.route('/faq')
def faq():
    return render_template('public/faq.html')

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for reaching out to Anti Matrix! Your query has been logged and our team will get in touch with you.', 'success')
        return redirect(url_for('main.contact'))
    return render_template('public/contact.html')

@main_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('public/privacy_policy.html')

@main_bp.route('/terms')
def terms():
    return render_template('public/terms.html')

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

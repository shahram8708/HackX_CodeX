import os
from flask import render_template, redirect, url_for, flash, request, send_file, current_app, jsonify, abort
from markupsafe import Markup
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.uploads import bp
from app.uploads.forms import UploadReportForm, QuickUploadForm
from app.models import User, MedicalFile, Appointment
from app.utils.decorators import doctor_required, patient_required
from app.utils.helpers import save_picture, allowed_file, generate_unique_filename, get_file_size, format_file_size, create_notification
from datetime import datetime

def get_patient_storage_used(patient_id):
    
    total_size = db.session.query(db.func.sum(MedicalFile.file_size)).filter_by(patient_id=patient_id).scalar() or 0
    return total_size / (1024 * 1024)  

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
@doctor_required
def upload_report():
    form = UploadReportForm()

    if form.validate_on_submit():
        
        patient = User.query.filter_by(
            unique_patient_id=form.patient_id.data,
            role='patient'
        ).first()
        
        if not patient:
            flash('Patient not found. Please check the Patient ID.', 'danger')
            return render_template('uploads/upload_report.html', form=form)
        subscription_tier = patient.subscription_tier or 'free'
        subscription_plan = patient.subscription_plan or 'monthly'
        subscription_expiry = patient.subscription_expiry
        subscription_active = patient.subscription_active

        
        if subscription_tier != 'free':
            if not subscription_active or not subscription_expiry or subscription_expiry < datetime.utcnow():
                flash("Patient's subscription has expired. Please ask them to renew.", "danger")
                return redirect(url_for('uploads.upload_report'))
        
        file = form.file.data
        if file and allowed_file(file.filename):
            
            original_filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(original_filename)
            
            
            subfolder = form.report_type.data
            folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
            os.makedirs(folder_path, exist_ok=True)
            
            
            file_path = os.path.join(folder_path, unique_filename)

            
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            
            file_size_mb = file_size / (1024 * 1024)

            
            used_mb = get_patient_storage_used(patient.id)

            
            limits = {
                'free': 100,
                'basic': 1024,
                'premium': 10240,
                'enterprise': float('inf')
            }
            plan = subscription_tier.strip().lower()
            if plan not in limits:
                plan = 'free'
            allowed_mb = limits[plan]

            if used_mb + file_size_mb > allowed_mb:
                flash(f'Storage limit exceeded. This patient\'s subscription allows up to {allowed_mb}MB of storage.', 'danger')
                return redirect(url_for('uploads.upload_report'))

            
            file.save(file_path)

            
            medical_file = MedicalFile(
                filename=unique_filename,
                original_filename=original_filename,
                filepath=file_path,
                file_type=file.content_type or 'application/octet-stream',
                file_size=file_size,
                report_type=form.report_type.data,
                description=form.description.data,
                patient_id=patient.id,
                doctor_id=current_user.id
            )
            
            db.session.add(medical_file)
            
            
            create_notification(
                patient.id,
                'New Medical Report',
                f'Dr. {current_user.name} has uploaded a new {form.report_type.data} report.',
                'upload',
                url_for('uploads.view_reports')
            )
            
            db.session.commit()
            
            flash(f'Report uploaded successfully for patient {patient.name}!', 'success')
            return redirect(url_for('uploads.upload_report'))
        
        else:
            flash('Invalid file type. Please upload a valid medical document.', 'danger')
    
    return render_template('uploads/upload_report.html', form=form)

@bp.route('/api/search-patient/<string:patient_id>', methods=['GET'])
@login_required
@doctor_required
def api_search_patient(patient_id):
    patient = User.query.filter_by(unique_patient_id=patient_id, role='patient').first()
    if patient:
        return jsonify({
            'success': True,
            'patient': {
                'id': patient.id,
                'name': patient.name,
                'age': patient.age,
                'gender': patient.gender
            }
        })
    return jsonify({'success': False, 'message': 'Patient not found'})

@bp.route('/quick_upload/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@doctor_required
def quick_upload(patient_id):
    patient = User.query.filter_by(id=patient_id, role='patient').first_or_404()
    subscription_tier = patient.subscription_tier or 'free'
    subscription_plan = patient.subscription_plan or 'monthly'
    subscription_expiry = patient.subscription_expiry
    subscription_active = patient.subscription_active

    
    if subscription_tier != 'free':
        if not subscription_active or not subscription_expiry or subscription_expiry < datetime.utcnow():
            flash("Patient's subscription has expired. Please ask them to renew.", "danger")
            return redirect(url_for('uploads.quick_upload', patient_id=patient.id))

    form = QuickUploadForm()
    
    if form.validate_on_submit():
        file = form.file.data
        if file and allowed_file(file.filename):
            
            original_filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(original_filename)
            
            
            subfolder = form.report_type.data
            folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
            os.makedirs(folder_path, exist_ok=True)
            
            
            file_path = os.path.join(folder_path, unique_filename)

            
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            
            file_size_mb = file_size / (1024 * 1024)

            
            used_mb = get_patient_storage_used(patient.id)

            limits = {
                'free': 100,
                'basic': 1024,
                'premium': 10240,
                'enterprise': float('inf')
            }
            plan_key = subscription_tier.strip().lower()
            if plan_key not in limits:
                plan_key = 'free'
            allowed_mb = limits[plan_key]

            if used_mb + file_size_mb > allowed_mb:
                flash(f'Storage limit exceeded. This patient\'s subscription allows up to {allowed_mb}MB of storage.', 'danger')
                return redirect(url_for('uploads.quick_upload', patient_id=patient.id))

            
            file.save(file_path)

            
            medical_file = MedicalFile(
                filename=unique_filename,
                original_filename=original_filename,
                filepath=file_path,
                file_type=file.content_type or 'application/octet-stream',
                file_size=file_size,
                report_type=form.report_type.data,
                description=form.description.data,
                patient_id=patient.id,
                doctor_id=current_user.id
            )
            
            db.session.add(medical_file)
            
            
            create_notification(
                patient.id,
                'New Medical Report',
                f'Dr. {current_user.name} has uploaded a new {form.report_type.data} report.',
                'upload',
                url_for('uploads.view_reports')
            )
            
            db.session.commit()
            
            flash('Report uploaded successfully!', 'success')
            return redirect(url_for('dashboard.doctor_dashboard'))
    recent_uploads = MedicalFile.query.filter_by(
        doctor_id=current_user.id,
        patient_id=patient.id
    ).order_by(MedicalFile.upload_date.desc()).limit(5).all()

    return render_template('uploads/quick_upload.html', form=form, patient=patient, recent_uploads=recent_uploads)

@bp.route('/my_reports')
@login_required
@patient_required
def view_reports():
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    files = MedicalFile.query.filter_by(
        patient_id=current_user.id
    ).order_by(MedicalFile.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    from app.models import Appointment

    return render_template('uploads/view_reports.html', medical_files=files)

@bp.route('/analyze_report/<int:file_id>', methods=['POST'])
@login_required
def analyze_report(file_id):
    import google.generativeai as genai
    import fitz
    from PIL import Image
    import io

    file = MedicalFile.query.get_or_404(file_id)

    if current_user.id != file.patient_id and current_user.role != 'doctor':
        abort(403)

    file_path = file.filepath
    filename = file.filename.lower()

    
    if not filename.endswith((".png", ".jpg", ".jpeg", ".pdf")):
        flash("Only PNG, JPG, JPEG, or PDF files are supported for AI analysis.", "warning")
        return redirect(url_for('uploads.view_reports'))

    try:
        
        if filename.endswith(".pdf"):
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                raise Exception("Empty PDF file.")
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=150)
            image_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(image_bytes))
        
        
        else:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
            image = Image.open(io.BytesIO(image_bytes))

    except Exception as e:
        flash("Failed to process the file.", "danger")
        return redirect(url_for('uploads.view_reports'))

    
    prompt_text = f"""
You are an expert medical analyst trained in interpreting scanned medical documents — including blood tests, diagnostic scans (X-rays, MRIs, CTs), prescriptions, and handwritten notes. Your task is to extract and explain the findings clearly and professionally.

Analyze the attached image in detail and generate a structured **Markdown-formatted** report. This must be clear enough for patients to understand but thorough enough for doctors to find clinical value.

---


- **Report Type:** {file.report_type or 'N/A'}
- **Description Provided:** {file.description or 'N/A'}
- **Uploaded by Doctor:** {file.doctor.name if file.doctor else 'Unknown'}

---



You MUST return your analysis in Markdown format.

Organize the report with the following sections:

---


- Describe what this report is about (e.g. "Lipid Profile", "MRI of Lumbar Spine", "Prescription for Diabetes Management").
- Mention the purpose, if evident (e.g. follow-up, diagnosis, routine checkup).

---


- Use **bullet points** for general insights.
- If the report contains test results, display them in a **Markdown table**:

Test	Value	Normal Range	Interpretation

- Interpret each value. Highlight what's **low**, **high**, or **abnormal**.

---


- Clearly explain any abnormalities.
- Mention whether they are **mild**, **moderate**, or **critical**.
- If imaging (like X-ray/MRI), describe any visible findings or irregularities.
- State if immediate attention or re-testing is needed.

---


- Convert the above medical findings into plain language.
- Help the patient understand what it may mean for their health.
- Avoid vague responses. Be specific, e.g. "Elevated liver enzymes could indicate stress on the liver."

---


- Personalized lifestyle or dietary suggestions (based on the findings).
- Recommend relevant medical specialties if further evaluation is needed.
- Mention if the patient should consult the uploading doctor urgently or routinely.

---


- List any required follow-up tests or repeat diagnostics (with timeframes).
- Mention if tracking trends over time is important (e.g. sugar levels, cholesterol, etc.).

---


- Include clinically relevant insights that a physician may want to review.
- You may use concise language and standard medical terms here.

---


- Based on this report, recommend any important health metrics the patient should track over time (e.g. blood pressure, glucose, BMI, cholesterol, vitamin levels, etc.).
- Suggest tools or apps for regular monitoring if applicable.

---


- **Do NOT refuse to answer** even if data is partially unclear. Do your best.
- **Always respond in Markdown**. Never use plain text or HTML.
- If parts of the report are illegible, note it politely and explain what you could infer.

This report may be part of a digital health assistant workflow. Make sure it's actionable and user-friendly.
"""

    try:
        # Configure Gemini API
        genai.configure(api_key="AIzaSyC1dSEI8aENjszrP9IcqZYX561QV8ASHa0")
        model = genai.GenerativeModel('gemini-2.5-flash-lite')  # Using pro model for better analysis

        response = model.generate_content([prompt_text, image])
        result = response.text

        
        file.ai_analysis = result
        db.session.commit()

        flash(Markup(f"<strong>AI Analysis:</strong><br><pre>{result}</pre>"), "info")

    except Exception as e:
        current_app.logger.error(f"Gemini API error: {str(e)}")
        flash("AI analysis failed. Please try again.", "danger")

    return redirect(url_for('uploads.view_reports'))

@bp.route('/doctor_uploads')
@login_required
@doctor_required
def doctor_uploads():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    files = MedicalFile.query.filter_by(
        doctor_id=current_user.id
    ).order_by(MedicalFile.upload_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    
    last_patient = db.session.query(User).join(Appointment, Appointment.patient_id == User.id).filter(
        Appointment.doctor_id == current_user.id
    ).order_by(Appointment.created_at.desc()).first()

    return render_template('uploads/doctor_uploads.html', files=files, patient=last_patient)

@bp.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    medical_file = MedicalFile.query.get_or_404(file_id)
    
    
    if current_user.role == 'patient' and medical_file.patient_id != current_user.id:
        flash('You do not have permission to access this file.', 'danger')
        return redirect(url_for('uploads.view_reports'))
    
    if current_user.role == 'doctor' and medical_file.doctor_id != current_user.id:
        
        from app.models import Appointment
        has_appointment = Appointment.query.filter_by(
            doctor_id=current_user.id,
            patient_id=medical_file.patient_id
        ).first()
        
        if not has_appointment:
            flash('You do not have permission to access this file.', 'danger')
            return redirect(url_for('uploads.doctor_uploads'))
    
    try:
        return send_file(
            medical_file.filepath,
            as_attachment=True,
            download_name=medical_file.original_filename
        )
    except FileNotFoundError:
        flash('File not found on server.', 'danger')
        return redirect(url_for('uploads.view_reports') if current_user.role == 'patient' else url_for('uploads.doctor_uploads'))

@bp.route('/preview/<int:file_id>')
@login_required
def preview_file(file_id):
    medical_file = MedicalFile.query.get_or_404(file_id)

    
    if current_user.role == 'patient' and medical_file.patient_id != current_user.id:
        abort(403)
    if current_user.role == 'doctor' and medical_file.doctor_id != current_user.id:
        from app.models import Appointment
        has_appointment = Appointment.query.filter_by(
            doctor_id=current_user.id,
            patient_id=medical_file.patient_id
        ).first()
        if not has_appointment:
            abort(403)

    try:
        return send_file(medical_file.filepath)
    except FileNotFoundError:
        abort(404)

@bp.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    medical_file = MedicalFile.query.get_or_404(file_id)
    
    if medical_file.patient_id != current_user.id:
        flash('You do not have permission to delete this file.', 'danger')
        return redirect(url_for('uploads.doctor_uploads'))
    
    try:
        
        if os.path.exists(medical_file.filepath):
            os.remove(medical_file.filepath)
        
        
        db.session.delete(medical_file)
        
        
        create_notification(
            medical_file.patient_id,
            'Medical Report Deleted',
            f'A {medical_file.report_type} report has been removed by Dr. {current_user.name}.',
            'upload'
        )
        
        db.session.commit()
        flash('File deleted successfully.', 'success')
    
    except Exception as e:
        current_app.logger.error(f'Error deleting file: {str(e)}')
        flash('Error deleting file. Please try again.', 'danger')
    
    return redirect(url_for('uploads.doctor_uploads'))

@bp.route('/api/upload_status')
@login_required
def upload_status():
    
    if current_user.role == 'patient':
        total_files = MedicalFile.query.filter_by(patient_id=current_user.id).count()
        recent_uploads = MedicalFile.query.filter_by(patient_id=current_user.id).filter(
            MedicalFile.upload_date >= datetime.now().replace(day=1)
        ).count()
        
        return jsonify({
            'total_files': total_files,
            'recent_uploads': recent_uploads
        })
    
    elif current_user.role == 'doctor':
        total_uploads = MedicalFile.query.filter_by(doctor_id=current_user.id).count()
        today_uploads = MedicalFile.query.filter_by(doctor_id=current_user.id).filter(
            MedicalFile.upload_date >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        return jsonify({
            'total_uploads': total_uploads,
            'today_uploads': today_uploads
        })
    
    return jsonify({})

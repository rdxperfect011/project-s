import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from flask import Response
import csv
from io import StringIO
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---- Models ----
class FeePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False)
    student_class = db.Column(db.String(50), nullable=False)
    parent_name = db.Column(db.String(120), nullable=False)
    parent_phone = db.Column(db.String(30), nullable=False)
    payment_month = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    receipt_filename = db.Column(db.String(300))
    paid = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FeePayment {self.id} {self.student_name} {self.roll_no}>"

# ---- Helpers ----
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# ---- Routes ----
@app.route("/")
def index():
    return render_template("index.html", school_name="Nav Yug Higher Secondary School")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        if not (name and email and message):
            flash("Please fill all fields.", "danger")
            return redirect(url_for("contact"))

        msg = ContactMessage(name=name, email=email, message=message)
        db.session.add(msg)
        db.session.commit()
        flash("Your message has been sent successfully!", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/schedule_visit", methods=["GET", "POST"])
def schedule_visit():
    if request.method == "POST":
        student_name = request.form.get("student_name", "").strip()
        parent_name = request.form.get("parent_name", "").strip()
        parent_phone = request.form.get("parent_phone", "").strip()
        student_class = request.form.get("student_class", "").strip()
        section = request.form.get("section", "").strip()
        visit_date_str = request.form.get("visit_date", "").strip()
        visit_time = request.form.get("visit_time", "").strip()
        purpose = request.form.get("purpose", "").strip()

        if not (student_name and parent_name and parent_phone and student_class and section and visit_date_str and visit_time and purpose):
            flash("Please fill all fields.", "danger")
            return redirect(url_for("schedule_visit"))

        try:
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("schedule_visit"))

        visit = Visit(
            student_name=student_name,
            parent_name=parent_name,
            parent_phone=parent_phone,
            student_class=f"{student_class} - Section {section}",
            visit_date=visit_date,
            visit_time=visit_time,
            purpose=purpose
        )
        db.session.add(visit)
        db.session.commit()
        flash("Your visit has been scheduled successfully! We will contact you to confirm.", "success")
        return redirect(url_for("schedule_visit"))
    
    return render_template("schedule_visit.html")

@app.route("/payment_history", methods=["GET", "POST"])
def payment_history():
    payments = None
    if request.method == "POST":
        roll_no = request.form.get("roll_no")
        if roll_no:
            payments = FeePayment.query.filter_by(roll_no=roll_no).all()
    return render_template("payment_history.html", payments=payments)

@app.route("/admin/download_csv")
def download_csv():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    payments = FeePayment.query.all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Student Name", "Roll No", "Class", "Parent Name", "Phone", "Month", "Amount", "Paid", "Date"])
    for p in payments:
        writer.writerow([p.id, p.student_name, p.roll_no, p.student_class, p.parent_name, p.parent_phone, p.payment_month, p.amount, p.paid, p.submitted_at])
    
    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=fee_data.csv"})

@app.route("/fee", methods=["GET", "POST"])
def fee_form():
    if request.method == "POST":
        # Collect form data
        student_name = request.form.get("student_name", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        student_class = request.form.get("student_class", "").strip()
        parent_name = request.form.get("parent_name", "").strip()
        parent_phone = request.form.get("parent_phone", "").strip()
        payment_month = request.form.get("payment_month", "").strip()
        amount = request.form.get("amount", "").strip()

        # Basic validation
        if not (student_name and roll_no and student_class and parent_name and parent_phone and payment_month and amount):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("fee_form"))

        try:
            amount_val = float(amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return redirect(url_for("fee_form"))

        # Handle file upload (optional)
        receipt_file = request.files.get("receipt")
        filename_on_disk = None
        if receipt_file and receipt_file.filename != "":
            if allowed_file(receipt_file.filename):
                safe_name = secure_filename(receipt_file.filename)
                # prefix filename with timestamp to avoid collisions
                timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                filename_on_disk = f"{timestamp}_{safe_name}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename_on_disk)
                receipt_file.save(save_path)
            else:
                flash("Receipt must be png/jpg/pdf.", "danger")
                return redirect(url_for("fee_form"))

        payment = FeePayment(
            student_name=student_name,
            roll_no=roll_no,
            student_class=student_class,
            parent_name=parent_name,
            parent_phone=parent_phone,
            payment_month=payment_month,
            amount=amount_val,
            receipt_filename=filename_on_disk,
            paid=False  # default false — admin will verify or you can implement auto verify
        )
        db.session.add(payment)
        db.session.commit()
        flash("Fee submission saved. Admin will verify and update status.", "success")
        return redirect(url_for("index"))

    return render_template("fee_form.html")

# Serve uploaded receipts
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---- Admin simple auth ----
def admin_logged_in():
    return session.get("admin_logged_in") == True

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u == app.config['ADMIN_USERNAME'] and p == app.config['ADMIN_PASSWORD']:
            session["admin_logged_in"] = True
            flash("Logged in as admin.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for("admin_login"))
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    # Get query parameters
    query = request.args.get('query', '').strip()
    filter_class = request.args.get('filter_class', '').strip()
    filter_status = request.args.get('filter_status', '').strip()
    
    # Start with base query
    payments_query = FeePayment.query
    
    # Apply search filters
    if query:
        payments_query = payments_query.filter(
            db.or_(
                FeePayment.student_name.ilike(f'%{query}%'),
                FeePayment.roll_no.ilike(f'%{query}%'),
                FeePayment.parent_name.ilike(f'%{query}%')
            )
        )
    
    if filter_class:
        payments_query = payments_query.filter(FeePayment.student_class == filter_class)
    
    if filter_status == 'paid':
        payments_query = payments_query.filter(FeePayment.paid == True)
    elif filter_status == 'pending':
        payments_query = payments_query.filter(FeePayment.paid == False)
    
    # Order and execute
    payments = payments_query.order_by(FeePayment.submitted_at.desc()).all()
    
    # Get unique classes for filter dropdown
    all_classes = db.session.query(FeePayment.student_class).distinct().all()
    classes = [c[0] for c in all_classes if c[0]]
    
    return render_template("admin_dashboard.html", payments=payments, classes=classes)

@app.route("/admin/bulk_mark_paid", methods=["POST"])
def admin_bulk_mark_paid():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    payment_ids = request.form.getlist('payment_ids')
    if not payment_ids:
        flash("No payments selected.", "danger")
        return redirect(url_for("admin_dashboard"))
    
    updated_count = 0
    for payment_id in payment_ids:
        try:
            payment = FeePayment.query.get(int(payment_id))
            if payment and not payment.paid:
                payment.paid = True
                updated_count += 1
        except (ValueError, AttributeError):
            continue
    
    db.session.commit()
    flash(f"{updated_count} payment(s) marked as PAID.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/bulk_delete", methods=["POST"])
def admin_bulk_delete():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    payment_ids = request.form.getlist('payment_ids')
    if not payment_ids:
        flash("No payments selected.", "danger")
        return redirect(url_for("admin_dashboard"))
    
    deleted_count = 0
    for payment_id in payment_ids:
        try:
            payment = FeePayment.query.get(int(payment_id))
            if payment:
                # delete receipt file if exists
                if payment.receipt_filename:
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], payment.receipt_filename))
                    except Exception:
                        pass
                db.session.delete(payment)
                deleted_count += 1
        except (ValueError, AttributeError):
            continue
    
    db.session.commit()
    flash(f"{deleted_count} payment(s) deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/mark_paid/<int:payment_id>", methods=["POST"])
def admin_mark_paid(payment_id):
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    payment = FeePayment.query.get_or_404(payment_id)
    payment.paid = True
    db.session.commit()
    flash(f"Payment {payment_id} marked as PAID.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete/<int:payment_id>", methods=["POST"])
def admin_delete(payment_id):
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    payment = FeePayment.query.get_or_404(payment_id)
    # delete receipt file if exists
    if payment.receipt_filename:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], payment.receipt_filename))
        except Exception:
            pass
    db.session.delete(payment)
    db.session.commit()
    flash(f"Payment {payment_id} deleted.", "info")
    return redirect(url_for("admin_dashboard"))
@app.route("/admin/students")
def admin_students():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    # Get filter parameter
    filter_class = request.args.get('filter_class', '').strip()
    
    # Get all students or filter by class
    if filter_class:
        students = Student.query.filter_by(student_class=filter_class).order_by(Student.student_class, Student.section, Student.name).all()
    else:
        students = Student.query.order_by(Student.student_class, Student.section, Student.name).all()
    
    # Group students by class and section
    students_by_class = {}
    for student in students:
        class_section_key = f"{student.student_class} - Section {student.section}"
        if class_section_key not in students_by_class:
            students_by_class[class_section_key] = []
        students_by_class[class_section_key].append(student)
    
    # Calculate total students
    total_students = len(students)
    
    # Get unique classes for filter dropdown
    all_classes = db.session.query(Student.student_class).distinct().all()
    classes = [c[0] for c in all_classes if c[0]]
    
    return render_template("admin_students.html", 
                         students_by_class=students_by_class, 
                         classes=classes, 
                         selected_class=filter_class,
                         total_students=total_students)

@app.route("/admin/add_student", methods=["POST"])
def admin_add_student():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))

    name = request.form.get("name")
    roll_no = request.form.get("roll_no")
    student_class = request.form.get("student_class")
    section = request.form.get("section")
    parent_name = request.form.get("parent_name")
    parent_phone = request.form.get("parent_phone")
    admission_date_str = request.form.get("admission_date")

    if not (name and roll_no and student_class and section and parent_name and parent_phone and admission_date_str):
        flash("Please fill all fields.", "danger")
        return redirect(url_for("admin_students"))

    # Check if roll number already exists
    if Student.query.filter_by(roll_no=roll_no).first():
        flash("Roll number already exists!", "danger")
        return redirect(url_for("admin_students"))

    try:
        admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid admission date format.", "danger")
        return redirect(url_for("admin_students"))

    student = Student(
        name=name,
        roll_no=roll_no,
        student_class=student_class,
        section=section,
        parent_name=parent_name,
        parent_phone=parent_phone,
        admission_date=admission_date
    )
    db.session.add(student)
    db.session.commit()
    flash("Student added successfully.", "success")
    return redirect(url_for("admin_students"))

@app.route("/admin/delete_student/<int:student_id>", methods=["POST"])
def admin_delete_student(student_id):
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash(f"Deleted student {student.name}.", "info")
    return redirect(url_for("admin_students"))

@app.route("/admin/visits")
def admin_visits():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    # Get filter parameters
    filter_status = request.args.get('filter_status', '').strip()
    filter_date = request.args.get('filter_date', '').strip()
    
    # Start with base query
    visits_query = Visit.query
    
    # Apply filters
    if filter_status:
        visits_query = visits_query.filter_by(status=filter_status)
    
    if filter_date:
        try:
            filter_date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
            visits_query = visits_query.filter(Visit.visit_date == filter_date_obj)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    # Order by visit date and time
    visits = visits_query.order_by(Visit.visit_date.asc(), Visit.visit_time.asc()).all()
    
    # Get unique statuses for filter dropdown
    statuses = ['scheduled', 'completed', 'cancelled']
    
    return render_template("admin_visits.html", 
                         visits=visits, 
                         statuses=statuses, 
                         selected_status=filter_status,
                         selected_date=filter_date)

@app.route("/admin/update_visit_status/<int:visit_id>", methods=["POST"])
def admin_update_visit_status(visit_id):
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    visit = Visit.query.get_or_404(visit_id)
    new_status = request.form.get("status")
    
    if new_status in ['scheduled', 'completed', 'cancelled']:
        visit.status = new_status
        db.session.commit()
        flash(f"Visit status updated to {new_status}.", "success")
    else:
        flash("Invalid status.", "danger")
    
    return redirect(url_for("admin_visits"))

@app.route("/admin/delete_visit/<int:visit_id>", methods=["POST"])
def admin_delete_visit(visit_id):
    if not admin_logged_in():
        return redirect(url_for("admin_login"))
    
    visit = Visit.query.get_or_404(visit_id)
    db.session.delete(visit)
    db.session.commit()
    flash(f"Deleted visit for {visit.student_name}.", "info")
    
    return redirect(url_for("admin_visits"))

# ---- Error handlers ----
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# ---- Models ----
class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    student_class = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False)  # A, B, C, etc.
    parent_name = db.Column(db.String(120), nullable=False)
    parent_phone = db.Column(db.String(20), nullable=False)
    admission_date = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f"<Student {self.name} ({self.roll_no})>"

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    parent_name = db.Column(db.String(120), nullable=False)
    parent_phone = db.Column(db.String(20), nullable=False)
    student_class = db.Column(db.String(50), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    visit_time = db.Column(db.String(20), nullable=False)
    purpose = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Visit {self.student_name} - {self.visit_date}>"
# ---- Run ----
if __name__ == "__main__":
    app.run(debug=True)
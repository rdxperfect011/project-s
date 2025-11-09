import os
from datetime import datetime
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
    payments = FeePayment.query.order_by(FeePayment.submitted_at.desc()).all()
    return render_template("admin_dashboard.html", payments=payments)

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
    students = Student.query.order_by(Student.student_class, Student.name).all()
    return render_template("admin_students.html", students=students)

@app.route("/admin/add_student", methods=["POST"])
def admin_add_student():
    if not admin_logged_in():
        return redirect(url_for("admin_login"))

    name = request.form.get("name")
    roll_no = request.form.get("roll_no")
    student_class = request.form.get("student_class")
    parent_name = request.form.get("parent_name")
    parent_phone = request.form.get("parent_phone")

    if not (name and roll_no and student_class and parent_name and parent_phone):
        flash("Please fill all fields.", "danger")
        return redirect(url_for("admin_students"))

    # Check if roll number already exists
    if Student.query.filter_by(roll_no=roll_no).first():
        flash("Roll number already exists!", "danger")
        return redirect(url_for("admin_students"))

    student = Student(
        name=name,
        roll_no=roll_no,
        student_class=student_class,
        parent_name=parent_name,
        parent_phone=parent_phone
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
    parent_name = db.Column(db.String(120), nullable=False)
    parent_phone = db.Column(db.String(20), nullable=False)
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Student {self.name} ({self.roll_no})>"
# ---- Run ----
if __name__ == "__main__":
    app.run(debug=True)
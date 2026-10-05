from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

import os

app = Flask(__name__)
app.secret_key = "aarocare-secret-key"

# SQLite database configuration
if os.environ.get("VERCEL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/aarocare.db"
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///aarocare.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    experience = db.Column(db.Integer, nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    patient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    doctor_name = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(20), nullable=False)
    appointment_time = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="Upcoming")

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:
            session["user_id"] = user.id
            session["user_name"] = user.name

            return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    print("SIGNUP ROUTE CALLED")
    print("METHOD:", request.method)

    if request.method == "POST":

        print("POST DATA:", request.form)

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "Email already registered. Please use a different email."

        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/doctors")
def doctors():

    if "user_id" not in session:
        return redirect(url_for("login"))

    doctors = Doctor.query.all()

    return render_template(
        "doctor-directory.html",
        doctors=doctors
    )


@app.route("/booking", methods=["GET", "POST"])
def booking():

    if "user_id" not in session:
        return redirect(url_for("login"))


    doctor = request.args.get("doctor")
    doctors = Doctor.query.all()


    if request.method == "POST":

        doctor_name = request.form["doctor_name"].strip()
        appointment_date = request.form["appointment_date"]
        appointment_time = request.form["appointment_time"]


        # Check if fields are empty
        if not doctor_name or not appointment_date or not appointment_time:
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="Please fill in all appointment details."
            )


        # Validate appointment date
        from datetime import date, datetime

        try:
            selected_date = date.fromisoformat(appointment_date)

        except ValueError:
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="Invalid appointment date."
            )


        # Prevent booking past dates
        if selected_date < date.today():
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="You cannot book an appointment for a past date."
            )


        # Validate appointment time
        try:
            selected_time = datetime.strptime(
                appointment_time,
                "%H:%M"
            ).time()

        except ValueError:
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="Invalid appointment time."
            )


        # Clinic hours: 9 AM - 11 PM
        clinic_start = datetime.strptime(
            "09:00",
            "%H:%M"
        ).time()

        clinic_end = datetime.strptime(
            "23:00",
            "%H:%M"
        ).time()


        if selected_time < clinic_start or selected_time > clinic_end:
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="Appointments are available between 9:00 AM and 11:00 PM."
            )


        # Check if doctor's slot is already booked
        existing_appointment = Appointment.query.filter_by(
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status="Upcoming"
        ).first()


        if existing_appointment:
            return render_template(
                "booking.html",
                doctor=doctor_name,
                doctors=doctors,
                error="This time slot is already booked. Please choose another time."
            )


        # Create appointment
        new_appointment = Appointment(
            patient_id=session["user_id"],
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status="Upcoming"
        )


        db.session.add(new_appointment)
        db.session.commit()


        flash(
            "Appointment booked successfully!",
            "success"
        )


        return redirect(url_for("dashboard"))


    return render_template(
        "booking.html",
        doctor=doctor,
        doctors=doctors
    )

@app.route("/cancel/<int:appointment_id>")
def cancel_appointment(appointment_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    appointment = Appointment.query.get_or_404(appointment_id)

    # Make sure the appointment belongs to the logged-in patient
    if appointment.patient_id != session["user_id"]:
        return "Unauthorized"

    from datetime import date

    appointment_date = date.fromisoformat(
        appointment.appointment_date
    )

    # Check if already cancelled
    if appointment.status == "Cancelled":
        flash("This appointment has already been cancelled.", "error")
        return redirect(url_for("dashboard"))

    # Prevent cancelling past appointments
    if appointment_date < date.today():
        flash("Past appointments cannot be cancelled.", "error")
        return redirect(url_for("dashboard"))

    # Cancel appointment
    appointment.status = "Cancelled"

    db.session.commit()

    flash("Appointment cancelled successfully.", "success")

    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    appointments = Appointment.query.filter_by(
        patient_id=session["user_id"]
    ).all()

    upcoming_appointments = []
    previous_appointments = []

    from datetime import datetime

    now = datetime.now()

    for appointment in appointments:

        # Combine appointment date and time
        appointment_datetime = datetime.strptime(
            appointment.appointment_date + " " + appointment.appointment_time,
            "%Y-%m-%d %H:%M"
        )

        # Upcoming only if the date AND time are still in the future
        if (
            appointment_datetime >= now
            and appointment.status == "Upcoming"
        ):
            upcoming_appointments.append(appointment)

        else:
            previous_appointments.append(appointment)

    return render_template(
        "dashboard.html",
        user=user,
        upcoming_appointments=upcoming_appointments,
        previous_appointments=previous_appointments
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

with app.app_context():
    db.create_all()

    if Doctor.query.count() == 0:
        doctors = [
            Doctor(
                name="Dr. Sharma",
                specialization="Cardiologist",
                experience=10
            ),
            Doctor(
                name="Dr. Patel",
                specialization="Dermatologist",
                experience=8
            ),
            Doctor(
                name="Dr. Gupta",
                specialization="Orthopedic Specialist",
                experience=12
            )
        ]

        db.session.add_all(doctors)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
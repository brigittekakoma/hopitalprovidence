from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager
user_roles=db.Table("user_roles",db.Column("user_id",db.ForeignKey("users.id"),primary_key=True),db.Column("role_id",db.ForeignKey("roles.id"),primary_key=True))
role_permissions=db.Table("role_permissions",db.Column("role_id",db.ForeignKey("roles.id"),primary_key=True),db.Column("permission_id",db.ForeignKey("permissions.id"),primary_key=True))
class User(UserMixin,db.Model):
    __tablename__="users"
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False)
    full_name=db.Column(db.String(160),nullable=False); password_hash=db.Column(db.String(255),nullable=False)
    active=db.Column(db.Boolean,default=True,nullable=False); created_at=db.Column(db.DateTime,default=datetime.utcnow)
    roles=db.relationship("Role",secondary=user_roles,back_populates="users")
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)
class Role(db.Model):
    __tablename__="roles"
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(80),unique=True,nullable=False)
    users=db.relationship("User",secondary=user_roles,back_populates="roles")
    permissions=db.relationship("Permission",secondary=role_permissions,back_populates="roles")
class Permission(db.Model):
    __tablename__="permissions"
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(100),unique=True,nullable=False); description=db.Column(db.String(255))
    roles=db.relationship("Role",secondary=role_permissions,back_populates="permissions")
class Patient(db.Model):
    __tablename__ = "patients"
    id = db.Column(db.Integer, primary_key=True)
    patient_number = db.Column(db.String(40), unique=True, nullable=False)
    full_name = db.Column(db.String(180), nullable=False)
    birth_date = db.Column(db.Date)
    sex = db.Column(db.String(20))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    address = db.Column(db.Text)
    emergency_contact = db.Column(db.String(160))
    blood_group = db.Column(db.String(5))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
class HospitalService(db.Model):
    __tablename__="hospital_services"
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),unique=True,nullable=False); description=db.Column(db.Text)
class Admission(db.Model):
    __tablename__="admissions"
    id=db.Column(db.Integer,primary_key=True); patient_id=db.Column(db.ForeignKey("patients.id"),nullable=False)
    service_id=db.Column(db.ForeignKey("hospital_services.id")); admitted_at=db.Column(db.DateTime,default=datetime.utcnow)
    discharged_at=db.Column(db.DateTime); status=db.Column(db.String(30),default="EN_COURS")
class ServiceItem(db.Model):
    __tablename__="service_items"
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(40),unique=True,nullable=False); name=db.Column(db.String(160),nullable=False)
class Tariff(db.Model):
    __tablename__="tariffs"
    id=db.Column(db.Integer,primary_key=True); service_item_id=db.Column(db.ForeignKey("service_items.id"),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False); currency=db.Column(db.String(3),default="CDF")
    valid_from=db.Column(db.Date,nullable=False); valid_to=db.Column(db.Date)
class Invoice(db.Model):
    __tablename__="invoices"
    id=db.Column(db.Integer,primary_key=True); invoice_number=db.Column(db.String(50),unique=True,nullable=False)
    admission_id=db.Column(db.ForeignKey("admissions.id"),nullable=True); patient_id=db.Column(db.ForeignKey("patients.id"),nullable=True, index=True); issued_at=db.Column(db.DateTime,default=datetime.utcnow)
    status=db.Column(db.String(30),default="BROUILLON"); currency=db.Column(db.String(3),nullable=False,default="CDF")
    admission=db.relationship("Admission", backref="invoices")
    patient=db.relationship("Patient", backref="invoices")
    lines=db.relationship("InvoiceLine", backref="invoice", cascade="all, delete-orphan")
    payments=db.relationship("Payment", backref="invoice", cascade="all, delete-orphan")
    @property
    def total(self):
        from decimal import Decimal
        return sum((line.line_total for line in self.lines), Decimal("0.00"))
    @property
    def paid_total(self):
        from decimal import Decimal
        return sum((p.amount for p in self.payments), Decimal("0.00"))
    @property
    def balance(self): return self.total - self.paid_total
class InvoiceLine(db.Model):
    __tablename__="invoice_lines"
    id=db.Column(db.Integer,primary_key=True); invoice_id=db.Column(db.ForeignKey("invoices.id"),nullable=False)
    service_item_id=db.Column(db.ForeignKey("service_items.id"),nullable=False); description_snapshot=db.Column(db.String(180),nullable=False)
    quantity=db.Column(db.Numeric(12,2),nullable=False); unit_price=db.Column(db.Numeric(14,2),nullable=False)
    @property
    def line_total(self): return self.quantity * self.unit_price
class Payment(db.Model):
    __tablename__="payments"
    id=db.Column(db.Integer,primary_key=True); invoice_id=db.Column(db.ForeignKey("invoices.id"),nullable=False)
    reference=db.Column(db.String(80),unique=True,nullable=False); amount=db.Column(db.Numeric(14,2),nullable=False)
    currency=db.Column(db.String(3),default="CDF"); method=db.Column(db.String(30),nullable=False)
    paid_at=db.Column(db.DateTime,default=datetime.utcnow); recorded_by=db.Column(db.ForeignKey("users.id"),nullable=False)

class InvoiceCoverageAuthorization(db.Model):
    """Dérogation financière validée : assurance, exemption, crédit ou urgence."""
    __tablename__ = "invoice_coverage_authorizations"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.ForeignKey("invoices.id"), nullable=False, index=True)
    coverage_type = db.Column(db.String(24), nullable=False)
    amount_covered = db.Column(db.Numeric(14,2), nullable=False)
    reference = db.Column(db.String(100))
    justification = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="VALIDEE")
    authorized_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    authorized_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    invoice = db.relationship("Invoice", backref=db.backref("coverage_authorizations", lazy=True, cascade="all, delete-orphan"))
    authorizer = db.relationship("User")

class CashSession(db.Model):
    __tablename__="cash_sessions"
    id=db.Column(db.Integer,primary_key=True); opened_by=db.Column(db.ForeignKey("users.id"),nullable=False)
    opened_at=db.Column(db.DateTime,default=datetime.utcnow); opening_balance=db.Column(db.Numeric(14,2),nullable=False)
    closed_at=db.Column(db.DateTime); closing_balance=db.Column(db.Numeric(14,2))
class Expense(db.Model):
    __tablename__="expenses"
    id=db.Column(db.Integer,primary_key=True); label=db.Column(db.String(180),nullable=False); category=db.Column(db.String(80),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False); currency=db.Column(db.String(3),default="CDF")
    incurred_at=db.Column(db.Date,nullable=False); status=db.Column(db.String(30),default="A_VALIDER")
    created_by=db.Column(db.ForeignKey("users.id"),nullable=False)
class Supplier(db.Model):
    __tablename__="suppliers"
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(180),nullable=False); phone=db.Column(db.String(40)); email=db.Column(db.String(160))
class StockItem(db.Model):
    __tablename__="stock_items"
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(50),unique=True,nullable=False)
    name=db.Column(db.String(180),nullable=False); unit=db.Column(db.String(30),nullable=False); alert_threshold=db.Column(db.Numeric(12,2),default=0)
class StockMovement(db.Model):
    __tablename__="stock_movements"
    id=db.Column(db.Integer,primary_key=True); item_id=db.Column(db.ForeignKey("stock_items.id"),nullable=False)
    movement_type=db.Column(db.String(20),nullable=False); quantity=db.Column(db.Numeric(12,2),nullable=False)
    reason=db.Column(db.String(255),nullable=False); occurred_at=db.Column(db.DateTime,default=datetime.utcnow)
    recorded_by=db.Column(db.ForeignKey("users.id"),nullable=False)
    item = db.relationship("StockItem")
class AuditLog(db.Model):
    __tablename__="audit_logs"
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.ForeignKey("users.id"))
    action=db.Column(db.String(120),nullable=False); entity=db.Column(db.String(80),nullable=False)
    entity_id=db.Column(db.String(80)); created_at=db.Column(db.DateTime,default=datetime.utcnow); details=db.Column(db.Text)
@login_manager.user_loader
def load_user(user_id): return db.session.get(User,int(user_id))


class Ward(db.Model):
    __tablename__ = "wards"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)

class HospitalRoom(db.Model):
    __tablename__ = "hospital_rooms"
    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.ForeignKey("wards.id"), nullable=False)
    room_number = db.Column(db.String(30), nullable=False)
    room_type = db.Column(db.String(40), default="STANDARD")
    active = db.Column(db.Boolean, default=True, nullable=False)
    ward = db.relationship("Ward", backref="rooms")
    __table_args__ = (db.UniqueConstraint("ward_id", "room_number", name="uq_room_per_ward"),)

class HospitalBed(db.Model):
    __tablename__ = "hospital_beds"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.ForeignKey("hospital_rooms.id"), nullable=False)
    bed_code = db.Column(db.String(30), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    room = db.relationship("HospitalRoom", backref="beds")

# Extend admission with a clinically neutral administrative lifecycle and bed assignment.
Admission.ward_id = db.Column(db.ForeignKey("wards.id"))
Admission.room_id = db.Column(db.ForeignKey("hospital_rooms.id"))
Admission.bed_id = db.Column(db.ForeignKey("hospital_beds.id"))
Admission.admission_reason = db.Column(db.Text)
Admission.discharge_note = db.Column(db.Text)
Admission.ward = db.relationship("Ward")
Admission.room = db.relationship("HospitalRoom")
Admission.bed = db.relationship("HospitalBed")
Admission.patient = db.relationship("Patient", backref="admissions")
Admission.service = db.relationship("HospitalService")

class StockBatch(db.Model):
    __tablename__ = "stock_batches"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.ForeignKey("stock_items.id"), nullable=False, index=True)
    batch_number = db.Column(db.String(80), nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = db.Column(db.Date, index=True)
    quantity_received = db.Column(db.Numeric(12, 2), nullable=False)
    quantity_remaining = db.Column(db.Numeric(12, 2), nullable=False)
    purchase_unit_cost = db.Column(db.Numeric(14, 2), default=0, nullable=False)
    supplier_id = db.Column(db.ForeignKey("suppliers.id"))
    storage_location = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True, nullable=False)
    item = db.relationship("StockItem", backref=db.backref("batches", lazy=True))
    supplier = db.relationship("Supplier")
    __table_args__ = (db.UniqueConstraint("item_id", "batch_number", name="uq_stock_batch_item_number"),)

class PharmacyDispense(db.Model):
    __tablename__ = "pharmacy_dispenses"
    id = db.Column(db.Integer, primary_key=True)
    dispense_number = db.Column(db.String(60), unique=True, nullable=False)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = db.Column(db.ForeignKey("admissions.id"))
    dispensed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    dispensed_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="VALIDEE", nullable=False)
    patient = db.relationship("Patient")
    admission = db.relationship("Admission")
    lines = db.relationship("PharmacyDispenseLine", backref="dispense", cascade="all, delete-orphan")

class PharmacyDispenseLine(db.Model):
    __tablename__ = "pharmacy_dispense_lines"
    id = db.Column(db.Integer, primary_key=True)
    dispense_id = db.Column(db.ForeignKey("pharmacy_dispenses.id"), nullable=False)
    batch_id = db.Column(db.ForeignKey("stock_batches.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    batch = db.relationship("StockBatch")


class LabTest(db.Model):
    __tablename__ = "lab_tests"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    specimen = db.Column(db.String(100))
    instructions = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)

class LabOrder(db.Model):
    __tablename__ = "lab_orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(70), unique=True, nullable=False)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = db.Column(db.ForeignKey("admissions.id"))
    test_id = db.Column(db.ForeignKey("lab_tests.id"), nullable=False)
    requested_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    priority = db.Column(db.String(20), default="NORMALE", nullable=False)
    clinical_note = db.Column(db.Text)
    specimen_collected_at = db.Column(db.DateTime)
    status = db.Column(db.String(24), default="DEMANDEE", nullable=False)
    patient = db.relationship("Patient")
    admission = db.relationship("Admission")
    test = db.relationship("LabTest")
    requester = db.relationship("User", foreign_keys=[requested_by])
    result = db.relationship("LabResult", back_populates="order", uselist=False, cascade="all, delete-orphan")

class LabResult(db.Model):
    __tablename__ = "lab_results"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey("lab_orders.id"), unique=True, nullable=False)
    result_value = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(40))
    reference_range = db.Column(db.String(120))
    interpretation = db.Column(db.Text)
    entered_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    entered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    validated_by = db.Column(db.ForeignKey("users.id"))
    validated_at = db.Column(db.DateTime)
    order = db.relationship("LabOrder", back_populates="result")
    author = db.relationship("User", foreign_keys=[entered_by])
    validator = db.relationship("User", foreign_keys=[validated_by])

class ClinicalConsultation(db.Model):
    __tablename__ = "clinical_consultations"
    id = db.Column(db.Integer, primary_key=True)
    consultation_number = db.Column(db.String(70), unique=True, nullable=False)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    admission_id = db.Column(db.ForeignKey("admissions.id"))
    clinician_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    consulted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    history = db.Column(db.Text)
    examination = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    care_plan = db.Column(db.Text)
    follow_up = db.Column(db.String(180))
    status = db.Column(db.String(24), default="BROUILLON", nullable=False)
    patient = db.relationship("Patient")
    admission = db.relationship("Admission")
    clinician = db.relationship("User")
    vitals = db.relationship("ConsultationVitals", back_populates="consultation", uselist=False, cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", back_populates="consultation", cascade="all, delete-orphan")

class ConsultationVitals(db.Model):
    __tablename__ = "consultation_vitals"
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.ForeignKey("clinical_consultations.id"), unique=True, nullable=False)
    temperature_c = db.Column(db.Numeric(4,1))
    systolic_mmhg = db.Column(db.Integer)
    diastolic_mmhg = db.Column(db.Integer)
    pulse_bpm = db.Column(db.Integer)
    respiratory_rate = db.Column(db.Integer)
    oxygen_percent = db.Column(db.Numeric(4,1))
    weight_kg = db.Column(db.Numeric(6,2))
    height_cm = db.Column(db.Numeric(6,2))
    pain_score = db.Column(db.Integer)
    notes = db.Column(db.Text)
    consultation = db.relationship("ClinicalConsultation", back_populates="vitals")

class Prescription(db.Model):
    __tablename__ = "prescriptions"
    id = db.Column(db.Integer, primary_key=True)
    prescription_number = db.Column(db.String(70), unique=True, nullable=False)
    consultation_id = db.Column(db.ForeignKey("clinical_consultations.id"), nullable=False)
    prescribed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    instructions = db.Column(db.Text)
    status = db.Column(db.String(24), default="EN_ATTENTE", nullable=False)
    consultation = db.relationship("ClinicalConsultation", back_populates="prescriptions")
    lines = db.relationship("PrescriptionLine", back_populates="prescription", cascade="all, delete-orphan")

class PrescriptionLine(db.Model):
    __tablename__ = "prescription_lines"
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.ForeignKey("prescriptions.id"), nullable=False)
    medicine_name = db.Column(db.String(180), nullable=False)
    dosage = db.Column(db.String(120), nullable=False)
    route = db.Column(db.String(80))
    frequency = db.Column(db.String(120))
    duration = db.Column(db.String(80))
    quantity = db.Column(db.String(80))
    directions = db.Column(db.Text)
    prescription = db.relationship("Prescription", back_populates="lines")

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    appointment_number = db.Column(db.String(70), unique=True, nullable=False)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    service_id = db.Column(db.ForeignKey("hospital_services.id"))
    professional_id = db.Column(db.ForeignKey("staff_profiles.id"), index=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    reason = db.Column(db.Text)
    status = db.Column(db.String(24), default="PLANIFIE", nullable=False)
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    patient = db.relationship("Patient")
    service = db.relationship("HospitalService")
    professional = db.relationship("StaffProfile")
    creator = db.relationship("User")


class OnlineAppointmentRequest(db.Model):
    __tablename__ = "online_appointment_requests"
    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(70), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(180), nullable=False)
    email = db.Column(db.String(160), nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=False)
    service_id = db.Column(db.ForeignKey("hospital_services.id"))
    preferred_date = db.Column(db.Date, nullable=False, index=True)
    preferred_period = db.Column(db.String(24), nullable=False, default="INDIFFERENT")
    reason = db.Column(db.String(500))
    status = db.Column(db.String(24), nullable=False, default="EN_ATTENTE", index=True)
    patient_id = db.Column(db.ForeignKey("patients.id"))
    appointment_id = db.Column(db.ForeignKey("appointments.id"))
    proposed_at = db.Column(db.DateTime)
    decision_note = db.Column(db.String(500))
    decided_by = db.Column(db.ForeignKey("users.id"))
    decided_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    service = db.relationship("HospitalService")
    patient = db.relationship("Patient")
    appointment = db.relationship("Appointment")

class ReceptionVisit(db.Model):
    __tablename__ = "reception_visits"
    id = db.Column(db.Integer, primary_key=True)
    visit_number = db.Column(db.String(70), unique=True, nullable=False)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    invoice_id = db.Column(db.ForeignKey("invoices.id"), nullable=True, index=True)
    appointment_id = db.Column(db.ForeignKey("appointments.id"))
    service_id = db.Column(db.ForeignKey("hospital_services.id"))
    visit_date = db.Column(db.Date, nullable=False, index=True)
    queue_number = db.Column(db.Integer, nullable=False)
    arrived_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    priority = db.Column(db.String(20), default="NORMALE", nullable=False)
    status = db.Column(db.String(24), default="EN_ATTENTE", nullable=False)
    reason = db.Column(db.Text)
    notes = db.Column(db.Text)
    registered_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    patient = db.relationship("Patient")
    invoice = db.relationship("Invoice", backref="reception_visits")
    appointment = db.relationship("Appointment")
    service = db.relationship("HospitalService")
    registrar = db.relationship("User")
    triage = db.relationship("TriageAssessment", back_populates="visit", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("visit_date", "queue_number", name="uq_queue_number_per_day"),)

class TriageAssessment(db.Model):
    __tablename__ = "triage_assessments"
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.ForeignKey("reception_visits.id"), unique=True, nullable=False)
    temperature_c = db.Column(db.Numeric(4,1))
    systolic_mmhg = db.Column(db.Integer)
    diastolic_mmhg = db.Column(db.Integer)
    pulse_bpm = db.Column(db.Integer)
    respiratory_rate = db.Column(db.Integer)
    oxygen_percent = db.Column(db.Numeric(4,1))
    weight_kg = db.Column(db.Numeric(6,2))
    height_cm = db.Column(db.Numeric(6,2))
    pain_score = db.Column(db.Integer)
    danger_signs = db.Column(db.Text)
    observations = db.Column(db.Text)
    assessed_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    assessed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    visit = db.relationship("ReceptionVisit", back_populates="triage")
    assessor = db.relationship("User")


class StaffProfile(db.Model):
    __tablename__ = "staff_profiles"
    id = db.Column(db.Integer, primary_key=True)
    employee_number = db.Column(db.String(40), unique=True, nullable=False)
    full_name = db.Column(db.String(180), nullable=False)
    job_title = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120))
    contract_type = db.Column(db.String(40))
    contract_reference = db.Column(db.String(100))
    hired_on = db.Column(db.Date)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    status = db.Column(db.String(30), default="ACTIF", nullable=False)
    user_id = db.Column(db.ForeignKey("users.id"), unique=True)
    user = db.relationship("User", backref=db.backref("staff_profile", uselist=False))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class ProfessionalSchedule(db.Model):
    __tablename__ = "professional_schedules"
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.ForeignKey("staff_profiles.id"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, nullable=False, default=30)
    active = db.Column(db.Boolean, nullable=False, default=True)
    staff = db.relationship("StaffProfile", backref=db.backref("consultation_schedules", lazy=True))
    __table_args__ = (db.UniqueConstraint("staff_id", "weekday", name="uq_professional_schedule_day"),)

class StaffAttendance(db.Model):
    __tablename__ = "staff_attendance"
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.ForeignKey("staff_profiles.id"), nullable=False)
    work_date = db.Column(db.Date, nullable=False)
    shift_label = db.Column(db.String(80))
    check_in = db.Column(db.Time)
    check_out = db.Column(db.Time)
    status = db.Column(db.String(30), nullable=False, default="PRESENT")
    note = db.Column(db.String(255))
    recorded_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    staff = db.relationship("StaffProfile", backref=db.backref("attendance_records", lazy=True))
    __table_args__ = (db.UniqueConstraint("staff_id", "work_date", name="uq_staff_attendance_day"),)

class StaffLeaveRequest(db.Model):
    __tablename__ = "staff_leave_requests"
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.ForeignKey("staff_profiles.id"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(30), nullable=False, default="EN_ATTENTE")
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = db.Column(db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    staff = db.relationship("StaffProfile", backref=db.backref("leave_requests", lazy=True))


class PayrollComponent(db.Model):
    __tablename__ = "payroll_components"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    component_type = db.Column(db.String(20), nullable=False)  # GAIN or RETENUE
    active = db.Column(db.Boolean, default=True, nullable=False)

class PayrollRecord(db.Model):
    __tablename__ = "payroll_records"
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.ForeignKey("staff_profiles.id"), nullable=False, index=True)
    period = db.Column(db.String(7), nullable=False, index=True)  # YYYY-MM
    currency = db.Column(db.String(3), nullable=False, default="CDF")
    base_amount = db.Column(db.Numeric(14,2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="BROUILLON")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False)
    staff = db.relationship("StaffProfile", backref=db.backref("payroll_records", lazy=True))
    lines = db.relationship("PayrollLine", backref="payroll", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("staff_id", "period", name="uq_payroll_staff_period"),)
    @property
    def gross(self):
        from decimal import Decimal
        return self.base_amount + sum((x.amount for x in self.lines if x.component.component_type == "GAIN"), Decimal("0.00"))
    @property
    def deductions(self):
        from decimal import Decimal
        return sum((x.amount for x in self.lines if x.component.component_type == "RETENUE"), Decimal("0.00"))
    @property
    def net(self): return self.gross - self.deductions

class PayrollLine(db.Model):
    __tablename__ = "payroll_lines"
    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.ForeignKey("payroll_records.id"), nullable=False)
    component_id = db.Column(db.ForeignKey("payroll_components.id"), nullable=False)
    amount = db.Column(db.Numeric(14,2), nullable=False)
    component = db.relationship("PayrollComponent")

class HomeSlide(db.Model):
    __tablename__ = "home_slides"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    subtitle = db.Column(db.String(300))
    image_url = db.Column(db.String(500))
    button_label = db.Column(db.String(80), default="Accéder à la plateforme")
    button_url = db.Column(db.String(300), default="/connexion")
    position = db.Column(db.Integer, default=0, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

# write test


class PatientPortalAccount(db.Model):
    __tablename__ = "patient_portal_accounts"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, unique=True, index=True)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255))
    activation_token_hash = db.Column(db.String(64), unique=True)
    activation_expires_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)
    patient = db.relationship("Patient", backref=db.backref("portal_account", uselist=False))
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return bool(self.password_hash and check_password_hash(self.password_hash, password))

class PatientAppointmentChangeRequest(db.Model):
    __tablename__ = "patient_appointment_change_requests"
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = db.Column(db.ForeignKey("appointments.id"), nullable=False, index=True)
    request_type = db.Column(db.String(20), nullable=False)
    requested_at = db.Column(db.DateTime)
    reason = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="EN_ATTENTE", index=True)
    decision_note = db.Column(db.String(500))
    decided_by = db.Column(db.ForeignKey("users.id"))
    decided_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    patient = db.relationship("Patient")
    appointment = db.relationship("Appointment")
    decision_maker = db.relationship("User")


class AppointmentNotification(db.Model):
    __tablename__ = "appointment_notifications"
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.ForeignKey("appointments.id"), nullable=False, index=True)
    reminder_type = db.Column(db.String(20), nullable=False)  # J-1 ou H-2
    recipient = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="EN_ATTENTE", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.String(500))
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    appointment = db.relationship("Appointment")
    __table_args__ = (db.UniqueConstraint("appointment_id", "reminder_type", name="uq_appointment_reminder_type"),)

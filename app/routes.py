from datetime import datetime, date, timedelta
from uuid import uuid4
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, send_file, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from . import db
from .models import Patient, Admission, Invoice, Payment, InvoiceCoverageAuthorization, Expense, StockItem, StockMovement, Supplier, StockBatch, PharmacyDispense, PharmacyDispenseLine, AuditLog, Ward, HospitalRoom, HospitalBed, HospitalService, ServiceItem, Tariff, InvoiceLine, LabTest, LabOrder, LabResult, ClinicalConsultation, ConsultationVitals, Prescription, PrescriptionLine, Appointment, OnlineAppointmentRequest, ProfessionalSchedule, ReceptionVisit, TriageAssessment, User, Role, Permission, StaffProfile, StaffAttendance, StaffLeaveRequest, PayrollComponent, PayrollRecord, PayrollLine, HomeSlide, PatientPortalAccount, PatientAppointmentChangeRequest, AppointmentNotification

bp = Blueprint("main", __name__)

# Catalogue des autorisations propres à l'Hôpital La Providence.
PERMISSION_CATALOG = {
    "dashboard.view": "Consulter le tableau de bord",
    "patients.view": "Consulter les dossiers administratifs",
    "patients.create": "Créer un dossier patient",
    "patients.edit": "Modifier un dossier patient",
    "patients.archive": "Archiver un dossier patient",
    "patients.portal_invite": "Inviter un patient à activer son portail personnel",
    "clinical.view": "Consulter les informations cliniques",
    "clinical.write": "Saisir une consultation ou un résultat",
    "clinical.validate": "Valider un résultat clinique ou biologique",
    "admissions.manage": "Gérer les admissions et sorties",
    "billing.view": "Consulter les factures et paiements",
    "billing.collect": "Enregistrer un encaissement",
    "billing.cancel": "Annuler une opération financière avec traçabilité",
    "billing.authorize_coverage": "Valider une assurance, exemption ou prise en charge",
    "pharmacy.manage": "Gérer la pharmacie et les stocks",
    "laboratory.manage": "Gérer les analyses de laboratoire",
    "reception.manage": "Gérer l'accueil, les rendez-vous et le triage",
    "notifications.view": "Consulter le journal des notifications de rendez-vous",
    "reports.view": "Consulter les rapports",
    "staff.manage": "Gérer les utilisateurs et les rôles",
    "hr.manage": "Gérer les dossiers RH, présences et congés",
    "settings.manage": "Gérer les paramètres du système",
    "audit.view": "Consulter le journal d'audit",
}

def user_has_permission(user, code):
    if not user or not user.is_authenticated or not user.active:
        return False
    return any(permission.code == code for role in user.roles for permission in role.permissions)

@bp.app_context_processor
def inject_access_helpers():
    return {"can_access": user_has_permission}


@bp.get("/")
def home():
    slides = HomeSlide.query.filter_by(active=True).order_by(HomeSlide.position.asc(), HomeSlide.id.asc()).all()
    return render_template("home.html", slides=slides)

@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", patients=Patient.query.count(),
        admissions=Admission.query.count(), invoices=Invoice.query.count(),
        payments=Payment.query.count(), expenses=Expense.query.count(),
        stock_items=StockItem.query.count())

@bp.get("/patients")
@login_required
def patients():
    term = request.args.get("q", "").strip()
    query = Patient.query
    if term:
        query = query.filter(or_(Patient.patient_number.ilike(f"%{term}%"),
            Patient.full_name.ilike(f"%{term}%"), Patient.phone.ilike(f"%{term}%")))
    records = query.order_by(Patient.created_at.desc()).limit(250).all()
    return render_template("patients/list.html", patients=records, search=term)

@bp.get("/patients/recherche-doublons")
@login_required
def patient_duplicate_search():
    """Recherche rapide de patients existants avant toute création de dossier."""
    term = " ".join(request.args.get("q", "").split())
    if len(term) < 3:
        return jsonify({"matches": []})
    matches = Patient.query.filter(Patient.full_name.ilike(f"%{term}%")).order_by(Patient.full_name.asc()).limit(8).all()
    return jsonify({"matches": [{
        "id": p.id, "name": p.full_name, "number": p.patient_number,
        "birth_date": p.birth_date.strftime("%d/%m/%Y") if p.birth_date else "Non renseignée",
        "phone": p.phone or "Non renseigné",
        "url": url_for("main.patient_detail", patient_id=p.id)
    } for p in matches]})


def _find_existing_patient(name, phone=None, birth_date=None):
    """Détecte une identité probable; ne fusionne jamais automatiquement deux personnes."""
    normalized = " ".join((name or "").casefold().split())
    if not normalized:
        return None
    candidates = Patient.query.filter(func.lower(func.trim(Patient.full_name)) == normalized).order_by(Patient.id.asc()).all()
    if not candidates:
        return None
    phone = (phone or "").strip()
    # Si date de naissance ou téléphone sont fournis, ils renforcent la correspondance.
    for candidate in candidates:
        same_birth = bool(birth_date and candidate.birth_date == birth_date)
        same_phone = bool(phone and candidate.phone and candidate.phone.strip() == phone)
        if (birth_date and same_birth) or (phone and same_phone) or (not birth_date and not phone):
            return candidate
    # Même nom mais éléments d'identification différents : signaler pour vérification humaine.
    return candidates[0]


@bp.route("/patients/new", methods=["GET", "POST"])
@login_required
def patient_new():
    if request.method == "POST":
        form = request.form
        number = ""
        name = " ".join(form.get("full_name", "").split())
        phone = form.get("phone", "").strip() or None
        birth_raw = form.get("birth_date", "").strip()
        errors = []
        if not name: errors.append("Le nom complet est obligatoire.")
        birth_date = None
        if birth_raw:
            try: birth_date = datetime.strptime(birth_raw, "%Y-%m-%d").date()
            except ValueError: errors.append("La date de naissance est invalide.")
        if not errors:
            existing = _find_existing_patient(name, phone, birth_date)
            if existing:
                flash(f"Un dossier correspondant existe déjà : {existing.patient_number} — {existing.full_name}. Vérifiez son identité avant toute nouvelle création.", "warning")
                return redirect(url_for("main.patient_detail", patient_id=existing.id))
        if errors:
            for error in errors: flash(error, "danger")
            return render_template("patients/form.html", form=form, page_title="Nouveau dossier patient")
        patient = Patient(patient_number=f"TEMP-{uuid4().hex}", full_name=name, phone=phone,
            sex=form.get("sex") or None, birth_date=birth_date,
            email=form.get("email", "").strip() or None,
            address=form.get("address", "").strip() or None,
            emergency_contact=form.get("emergency_contact", "").strip() or None,
            blood_group=form.get("blood_group", "").strip() or None)
        db.session.add(patient)
        db.session.flush()
        patient.patient_number = f"HLP-{datetime.utcnow().year}-{patient.id:06d}"
        db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="Patient",
            entity_id=str(patient.id), details="Création du dossier administratif patient"))
        db.session.commit()
        flash("Le dossier patient a été créé. Sa carte est disponible immédiatement.", "success")
        return redirect(url_for("main.patient_card", patient_id=patient.id))
    return render_template("patients/form.html", form={}, page_title="Nouveau dossier patient")


@bp.get("/patients/<int:patient_id>")
@login_required
def patient_detail(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    _record_sensitive_access("CONSULTATION_DOSSIER_PATIENT", "Patient", patient.id, "Ouverture du dossier administratif")
    return render_template("patients/detail.html", patient=patient, visits=ReceptionVisit.query.filter_by(patient_id=patient.id).order_by(ReceptionVisit.arrived_at.desc()).all())

@bp.route("/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@login_required
def patient_edit(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    if request.method == "POST":
        form = request.form
        number = form.get("patient_number", "").strip()
        name = " ".join(form.get("full_name", "").split())
        duplicate = Patient.query.filter(Patient.patient_number == number, Patient.id != patient.id).first()
        errors = []
        if not number or not name: errors.append("Le numéro du patient et le nom complet sont obligatoires.")
        if duplicate: errors.append("Ce numéro de dossier est déjà attribué.")
        raw_date = form.get("birth_date", "").strip()
        try: birth_date = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
        except ValueError: birth_date = None; errors.append("La date de naissance est invalide.")
        if errors:
            for error in errors: flash(error, "danger")
            return render_template("patients/form.html", form=form, page_title="Modifier le dossier patient")
        patient.patient_number=number; patient.full_name=name; patient.sex=form.get("sex") or None
        patient.birth_date=birth_date; patient.phone=form.get("phone", "").strip() or None
        patient.email=form.get("email", "").strip() or None; patient.address=form.get("address", "").strip() or None
        patient.emergency_contact=form.get("emergency_contact", "").strip() or None; patient.blood_group=form.get("blood_group", "").strip() or None
        db.session.add(AuditLog(user_id=current_user.id, action="MODIFICATION", entity="Patient", entity_id=str(patient.id), details="Mise à jour du dossier administratif patient"))
        db.session.commit(); flash("Le dossier patient a été mis à jour.", "success")
        return redirect(url_for("main.patient_detail", patient_id=patient.id))
    form={"patient_number":patient.patient_number,"full_name":patient.full_name,"sex":patient.sex or "","birth_date":patient.birth_date.isoformat() if patient.birth_date else "","phone":patient.phone or "","email":patient.email or "","address":patient.address or "","emergency_contact":patient.emergency_contact or "","blood_group":patient.blood_group or ""}
    return render_template("patients/form.html", form=form, page_title="Modifier le dossier patient")


@bp.post("/patients/<int:patient_id>/delete")
@login_required
def patient_delete(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    # Keep the patient record if it is referenced by any admission or financial history.
    if Admission.query.filter_by(patient_id=patient.id).first():
        flash("Suppression impossible : ce dossier est lié à un séjour. Il doit être archivé selon la procédure de conservation.", "warning")
        return redirect(url_for("main.patient_detail", patient_id=patient.id))
    db.session.add(AuditLog(user_id=current_user.id, action="SUPPRESSION", entity="Patient", entity_id=str(patient.id), details=f"Suppression du dossier {patient.patient_number}"))
    db.session.delete(patient); db.session.commit()
    flash("Dossier patient supprimé.", "success")
    return redirect(url_for("main.patients"))


@bp.get("/patients/<int:patient_id>/download")
@login_required
def patient_download(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from io import BytesIO
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="HospitalTitle", parent=styles["Title"], textColor=colors.HexColor("#245c48"), alignment=0))
        story = [Paragraph("HÔPITAL LA PROVIDENCE", styles["HospitalTitle"]), Paragraph("FICHE ADMINISTRATIVE DU PATIENT", styles["Heading2"]), Spacer(1, 8*mm)]
        rows = [["Rubrique", "Information"], ["Numéro de dossier", patient.patient_number], ["Nom complet", patient.full_name], ["Sexe", patient.sex or "Non précisé"], ["Date de naissance", patient.birth_date.strftime("%d/%m/%Y") if patient.birth_date else "Non renseignée"], ["Téléphone", patient.phone or "Non renseigné"], ["E-mail", patient.email or "Non renseigné"], ["Groupe sanguin", patient.blood_group or "Non renseigné"], ["Contact d'urgence", patient.emergency_contact or "Non renseigné"], ["Adresse", patient.address or "Non renseignée"], ["Création du dossier", patient.created_at.strftime("%d/%m/%Y %H:%M") if patient.created_at else "—"]]
        table = Table(rows, colWidths=[48*mm, 112*mm])
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#245c48")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#d6e2da")),("BACKGROUND",(0,1),(0,-1),colors.HexColor("#eff5f0")),("PADDING",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story += [table, Spacer(1, 8*mm), Paragraph("Document administratif. Les informations cliniques détaillées sont conservées dans un espace à accès restreint.", styles["BodyText"])]
        doc.build(story); buffer.seek(0)
        return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=f"Fiche_patient_{patient.patient_number}.pdf")
    except ImportError:
        flash("Le composant PDF n'est pas installé. Utilisez Imprimer puis Enregistrer en PDF.", "warning")
        return redirect(url_for("main.patient_detail", patient_id=patient.id))


@bp.get("/admissions")
@login_required
def admissions():
    records = Admission.query.order_by(Admission.admitted_at.desc()).limit(300).all()
    return render_template("admissions/list.html", admissions=records)

@bp.route("/admissions/new", methods=["GET", "POST"])
@login_required
def admission_new():
    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    wards = Ward.query.filter_by(active=True).order_by(Ward.name).all()
    services = HospitalService.query.order_by(HospitalService.name).all()
    beds = HospitalBed.query.filter_by(active=True).all()
    occupied_ids = {a.bed_id for a in Admission.query.filter_by(status="EN_COURS").all() if a.bed_id}
    available_beds = [b for b in beds if b.id not in occupied_ids]
    if request.method == "POST":
        form = request.form
        errors = []
        try:
            patient_id = int(form.get("patient_id", ""))
            patient = db.get_or_404(Patient, patient_id)
        except (ValueError, TypeError):
            patient = None; errors.append("Sélectionnez un patient valide.")
        bed = None
        bed_raw = form.get("bed_id", "").strip()
        if bed_raw:
            try:
                bed = db.get_or_404(HospitalBed, int(bed_raw))
                if not bed.active or bed.id in occupied_ids: errors.append("Ce lit n'est plus disponible.")
            except (ValueError, TypeError): errors.append("Le lit sélectionné est invalide.")
        if patient and Admission.query.filter_by(patient_id=patient.id, status="EN_COURS").first():
            errors.append("Ce patient possède déjà une hospitalisation en cours.")
        if errors:
            for e in errors: flash(e, "danger")
            return render_template("admissions/form.html", patients=patients, wards=wards, services=services, beds=available_beds, form=form)
        admission = Admission(patient_id=patient.id, service_id=int(form["service_id"]) if form.get("service_id") else None,
            ward_id=bed.room.ward_id if bed else None, room_id=bed.room_id if bed else None, bed_id=bed.id if bed else None,
            admission_reason=form.get("admission_reason", "").strip() or None, status="EN_COURS")
        db.session.add(admission); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="Admission", entity_id=str(admission.id), details="Ouverture d'une hospitalisation"))
        db.session.commit(); flash("Hospitalisation enregistrée.", "success")
        return redirect(url_for("main.admissions"))
    return render_template("admissions/form.html", patients=patients, wards=wards, services=services, beds=available_beds, form={})

@bp.post("/admissions/<int:admission_id>/discharge")
@login_required
def admission_discharge(admission_id):
    admission = db.get_or_404(Admission, admission_id)
    if admission.status != "EN_COURS":
        flash("Cette hospitalisation n'est plus en cours.", "warning")
    else:
        admission.status = "TERMINEE"; admission.discharged_at = datetime.utcnow()
        admission.discharge_note = request.form.get("discharge_note", "").strip() or None
        db.session.add(AuditLog(user_id=current_user.id, action="SORTIE", entity="Admission", entity_id=str(admission.id), details="Clôture administrative du séjour"))
        db.session.commit(); flash("Sortie administrative enregistrée.", "success")
    return redirect(url_for("main.admissions"))


@bp.get("/admissions/capacites")
@login_required
def admission_capacity():
    return render_template("admissions/capacity.html", wards=Ward.query.order_by(Ward.name).all())

@bp.post("/admissions/capacites/unite")
@login_required
def ward_create():
    name = request.form.get("name", "").strip()
    if not name: flash("Le nom de l'unité est obligatoire.", "danger")
    elif Ward.query.filter(func.lower(Ward.name) == name.lower()).first(): flash("Cette unité existe déjà.", "warning")
    else:
        row=Ward(name=name, description=request.form.get("description", "").strip() or None)
        db.session.add(row); db.session.flush(); db.session.add(AuditLog(user_id=current_user.id,action="CREATION",entity="Unité",entity_id=str(row.id),details="Création d'une unité d'hospitalisation")); db.session.commit(); flash("Unité créée.","success")
    return redirect(url_for("main.admission_capacity"))

@bp.post("/admissions/capacites/chambre")
@login_required
def room_create():
    try: ward=db.get_or_404(Ward,int(request.form.get("ward_id", "")))
    except (ValueError,TypeError): flash("Sélectionnez une unité valide.","danger"); return redirect(url_for("main.admission_capacity"))
    number=request.form.get("room_number", "").strip()
    if not number: flash("Le numéro de chambre est obligatoire.","danger")
    elif HospitalRoom.query.filter_by(ward_id=ward.id,room_number=number).first(): flash("Cette chambre existe déjà dans cette unité.","warning")
    else: db.session.add(HospitalRoom(ward_id=ward.id,room_number=number,room_type=request.form.get("room_type") or "STANDARD")); db.session.commit(); flash("Chambre créée.","success")
    return redirect(url_for("main.admission_capacity"))

@bp.post("/admissions/capacites/lit")
@login_required
def bed_create():
    try: room=db.get_or_404(HospitalRoom,int(request.form.get("room_id", "")))
    except (ValueError,TypeError): flash("Sélectionnez une chambre valide.","danger"); return redirect(url_for("main.admission_capacity"))
    code=request.form.get("bed_code", "").strip()
    if not code: flash("Le code du lit est obligatoire.","danger")
    elif HospitalBed.query.filter_by(bed_code=code).first(): flash("Ce code de lit existe déjà.","warning")
    else: db.session.add(HospitalBed(room_id=room.id,bed_code=code)); db.session.commit(); flash("Lit créé.","success")
    return redirect(url_for("main.admission_capacity"))


# --- Facturation et caisse : montants décimaux et séparation stricte des devises ---
def _money(value):
    try:
        amount = Decimal(str(value).replace(" ", "").replace(",", "."))
        if not amount.is_finite() or amount < 0: raise InvalidOperation
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Saisissez un montant positif valide.")

@bp.get("/facturation")
@login_required
def billing():
    invoices = Invoice.query.order_by(Invoice.issued_at.desc()).limit(250).all()
    admissions_rows = Admission.query.filter_by(status="EN_COURS").order_by(Admission.admitted_at.desc()).all()
    items = ServiceItem.query.order_by(ServiceItem.name).all()
    tariffs = Tariff.query.filter((Tariff.valid_to.is_(None)) | (Tariff.valid_to >= date.today())).all()
    return render_template("billing/index.html", invoices=invoices, admissions=admissions_rows, items=items, tariffs=tariffs)

@bp.post("/facturation/prestations")
@login_required
def service_item_create():
    code=request.form.get("code", "").strip().upper(); name=request.form.get("name", "").strip()
    if not code or not name:
        flash("Le code et le libellé de la prestation sont obligatoires.", "danger")
    elif ServiceItem.query.filter_by(code=code).first():
        flash("Ce code de prestation existe déjà.", "warning")
    else:
        item=ServiceItem(code=code,name=name); db.session.add(item); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id,action="CREATION",entity="Prestation",entity_id=str(item.id),details=f"Création de la prestation {code}")); db.session.commit()
        flash("Prestation ajoutée au catalogue.", "success")
    return redirect(url_for("main.billing"))

@bp.post("/facturation/tarifs")
@login_required
def tariff_create():
    try:
        item=db.get_or_404(ServiceItem,int(request.form.get("service_item_id", "")))
        amount=_money(request.form.get("amount")); currency=request.form.get("currency", "CDF").upper()
        if currency not in {"CDF","USD"}: raise ValueError("Devise non autorisée.")
        valid_from=datetime.strptime(request.form.get("valid_from", ""), "%Y-%m-%d").date()
        row=Tariff(service_item_id=item.id,amount=amount,currency=currency,valid_from=valid_from)
        db.session.add(row); db.session.flush(); db.session.add(AuditLog(user_id=current_user.id,action="CREATION",entity="Tarif",entity_id=str(row.id),details=f"Tarif {item.code} {amount} {currency}")); db.session.commit()
        flash("Tarif enregistré.", "success")
    except (ValueError,TypeError,InvalidOperation):
        db.session.rollback(); flash("Tarif invalide. Vérifiez la prestation, le montant, la devise et la date.", "danger")
    return redirect(url_for("main.billing"))

@bp.post("/facturation/factures")
@login_required
def invoice_create():
    try:
        admission=db.get_or_404(Admission,int(request.form.get("admission_id", "")))
        item=db.get_or_404(ServiceItem,int(request.form.get("service_item_id", "")))
        quantity=_money(request.form.get("quantity", "1")); price=_money(request.form.get("unit_price")); currency=request.form.get("currency", "CDF").upper()
        if admission.status != "EN_COURS": raise ValueError("Le séjour sélectionné n'est pas en cours.")
        if quantity <= 0 or price <= 0: raise ValueError("La quantité et le prix doivent être supérieurs à zéro.")
        if currency not in {"CDF","USD"}: raise ValueError("Devise non autorisée.")
        number=f"LP-{datetime.utcnow():%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}"
        invoice=Invoice(invoice_number=number,admission_id=admission.id,currency=currency,status="EMISE")
        db.session.add(invoice); db.session.flush()
        db.session.add(InvoiceLine(invoice_id=invoice.id,service_item_id=item.id,description_snapshot=item.name,quantity=quantity,unit_price=price))
        db.session.add(AuditLog(user_id=current_user.id,action="CREATION",entity="Facture",entity_id=str(invoice.id),details=f"Facture {number} émise en {currency}")); db.session.commit()
        flash(f"Facture {number} créée.", "success"); return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))
    except (ValueError,TypeError,InvalidOperation):
        db.session.rollback(); flash("Facture non créée : vérifiez les champs et la devise.", "danger"); return redirect(url_for("main.billing"))

@bp.get("/facturation/<int:invoice_id>")
@login_required
def invoice_detail(invoice_id):
    invoice=db.get_or_404(Invoice,invoice_id)
    return render_template("billing/detail.html",invoice=invoice)

@bp.post("/facturation/<int:invoice_id>/paiements")
@login_required
def payment_create(invoice_id):
    invoice=db.get_or_404(Invoice,invoice_id)
    try:
        amount=_money(request.form.get("amount")); method=request.form.get("method", "").strip().upper()
        if amount <= 0: raise ValueError("Le paiement doit être supérieur à zéro.")
        if amount > invoice.balance: raise ValueError("Le paiement dépasse le solde de cette facture.")
        if method not in {"ESPECES","MOBILE_MONEY","BANQUE","ASSURANCE"}: raise ValueError("Mode de paiement invalide.")
        reference=request.form.get("reference", "").strip() or f"PAY-{datetime.utcnow():%y%m%d%H%M%S}-{current_user.id}"
        if Payment.query.filter_by(reference=reference).first(): raise ValueError("Cette référence de paiement existe déjà.")
        payment=Payment(invoice_id=invoice.id,reference=reference,amount=amount,currency=invoice.currency,method=method,recorded_by=current_user.id)
        db.session.add(payment); db.session.flush()
        if invoice.balance == amount: invoice.status="PAYEE"
        else: invoice.status="PARTIELLE"
        db.session.add(AuditLog(user_id=current_user.id,action="PAIEMENT",entity="Facture",entity_id=str(invoice.id),details=f"Paiement {amount} {invoice.currency}, référence {reference}")); db.session.commit()
        flash("Paiement enregistré. Le reçu peut être imprimé.", "success")
    except (ValueError,TypeError,InvalidOperation) as exc:
        db.session.rollback(); flash(str(exc), "danger")
    return redirect(url_for("main.invoice_detail",invoice_id=invoice.id))

@bp.get("/facturation/recu/<int:payment_id>")
@login_required
def payment_receipt(payment_id):
    payment=db.get_or_404(Payment,payment_id)
    size = request.args.get("format", "80mm").lower()
    if size not in {"58mm", "80mm", "a4"}: size = "80mm"
    return render_template("billing/receipt.html",payment=payment, receipt_format=size)

# Pharmacie et stocks — lots tracés, sorties selon FEFO (expiration la plus proche).
@bp.get('/pharmacie')
@login_required
def pharmacy():
    items = StockItem.query.order_by(StockItem.name.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
    batches = StockBatch.query.filter_by(active=True).order_by(StockBatch.expiry_date.asc()).limit(300).all()
    today = date.today()
    summaries = []
    for item in items:
        lots = [b for b in item.batches if b.active]
        total = sum((Decimal(str(b.quantity_remaining)) for b in lots), Decimal('0.00'))
        threshold = Decimal(str(item.alert_threshold or 0))
        next_expiry = min((b.expiry_date for b in lots if b.quantity_remaining > 0 and b.expiry_date), default=None)
        summaries.append({'item': item, 'quantity': total, 'low': total <= threshold, 'next_expiry': next_expiry,
                          'expired': any(b.expiry_date and b.expiry_date < today and b.quantity_remaining > 0 for b in lots)})
    return render_template('pharmacy/index.html', summaries=summaries, suppliers=suppliers, batches=batches, today=today, patients=Patient.query.order_by(Patient.full_name.asc()).all())

@bp.post('/pharmacie/produits')
@login_required
def pharmacy_item_create():
    code = request.form.get('code', '').strip().upper()
    name = ' '.join(request.form.get('name', '').split())
    unit = request.form.get('unit', '').strip()
    try:
        threshold = Decimal(request.form.get('alert_threshold', '0'))
        if threshold < 0: raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash('Le seuil d’alerte doit être un nombre positif ou nul.', 'danger'); return redirect(url_for('main.pharmacy'))
    if not code or not name or not unit:
        flash('Code, désignation et unité sont obligatoires.', 'danger')
    elif StockItem.query.filter_by(code=code).first():
        flash('Ce code produit existe déjà.', 'warning')
    else:
        item = StockItem(code=code, name=name, unit=unit, alert_threshold=threshold)
        db.session.add(item); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id, action='CREATION', entity='ProduitStock', entity_id=str(item.id), details=f'Création du produit {code}'))
        db.session.commit(); flash('Produit enregistré.', 'success')
    return redirect(url_for('main.pharmacy'))

@bp.post('/pharmacie/fournisseurs')
@login_required
def pharmacy_supplier_create():
    name = request.form.get('name', '').strip()
    if not name: flash('Le nom du fournisseur est obligatoire.', 'danger')
    else:
        supplier = Supplier(name=name, phone=request.form.get('phone', '').strip() or None, email=request.form.get('email', '').strip() or None)
        db.session.add(supplier); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id, action='CREATION', entity='Fournisseur', entity_id=str(supplier.id), details=f'Création du fournisseur {name}'))
        db.session.commit(); flash('Fournisseur enregistré.', 'success')
    return redirect(url_for('main.pharmacy'))

@bp.post('/pharmacie/approvisionnements')
@login_required
def pharmacy_receive_batch():
    try:
        item = db.get_or_404(StockItem, int(request.form.get('item_id', '')))
        quantity = Decimal(request.form.get('quantity', '0'))
        cost = Decimal(request.form.get('purchase_unit_cost', '0'))
        expiry_raw = request.form.get('expiry_date', '').strip()
        expiry = datetime.strptime(expiry_raw, '%Y-%m-%d').date() if expiry_raw else None
        supplier_raw = request.form.get('supplier_id', '').strip()
        supplier = db.get_or_404(Supplier, int(supplier_raw)) if supplier_raw else None
        if quantity <= 0 or cost < 0: raise ValueError
    except (ValueError, InvalidOperation, TypeError):
        db.session.rollback(); flash('Vérifiez le produit, la quantité, le coût et la date de péremption.', 'danger'); return redirect(url_for('main.pharmacy'))
    number = request.form.get('batch_number', '').strip()
    if not number:
        flash('Le numéro de lot est obligatoire.', 'danger'); return redirect(url_for('main.pharmacy'))
    if StockBatch.query.filter_by(item_id=item.id, batch_number=number).first():
        flash('Ce numéro de lot existe déjà pour ce produit.', 'warning'); return redirect(url_for('main.pharmacy'))
    batch = StockBatch(item_id=item.id, batch_number=number, expiry_date=expiry, quantity_received=quantity,
        quantity_remaining=quantity, purchase_unit_cost=cost, supplier=supplier,
        storage_location=request.form.get('storage_location', '').strip() or None)
    db.session.add(batch); db.session.flush()
    db.session.add(StockMovement(item_id=item.id, movement_type='ENTREE', quantity=quantity,
        reason=f'Réception du lot {number}', recorded_by=current_user.id))
    db.session.add(AuditLog(user_id=current_user.id, action='APPROVISIONNEMENT', entity='StockBatch', entity_id=str(batch.id), details=f'{item.code} / lot {number} / quantité {quantity}'))
    db.session.commit(); flash('Lot réceptionné et stock mis à jour.', 'success')
    return redirect(url_for('main.pharmacy'))

@bp.post('/pharmacie/dispensations')
@login_required
def pharmacy_dispense():
    try:
        patient = db.get_or_404(Patient, int(request.form.get('patient_id', '')))
        item = db.get_or_404(StockItem, int(request.form.get('item_id', '')))
        quantity = Decimal(request.form.get('quantity', '0'))
        if quantity <= 0: raise ValueError
    except (ValueError, InvalidOperation, TypeError):
        flash('Sélectionnez un patient, un produit et une quantité valide.', 'danger'); return redirect(url_for('main.pharmacy'))
    # Lots non périmés uniquement, triés FEFO. La transaction est atomique.
    today = date.today()
    lots = StockBatch.query.filter(StockBatch.item_id == item.id, StockBatch.active.is_(True),
        StockBatch.quantity_remaining > 0, or_(StockBatch.expiry_date.is_(None), StockBatch.expiry_date >= today))\
        .order_by(StockBatch.expiry_date.is_(None), StockBatch.expiry_date.asc(), StockBatch.received_at.asc()).with_for_update().all()
    available = sum((Decimal(str(b.quantity_remaining)) for b in lots), Decimal('0.00'))
    if available < quantity:
        flash(f'Stock insuffisant ou lots périmés. Disponible : {available} {item.unit}.', 'danger'); return redirect(url_for('main.pharmacy'))
    dispense = PharmacyDispense(dispense_number=f'DSP-{datetime.utcnow():%Y%m%d%H%M%S%f}-{current_user.id}',
        patient_id=patient.id, dispensed_by=current_user.id, notes=request.form.get('notes', '').strip() or None)
    db.session.add(dispense); db.session.flush()
    remaining = quantity
    for batch in lots:
        if remaining <= 0: break
        take = min(Decimal(str(batch.quantity_remaining)), remaining)
        batch.quantity_remaining = Decimal(str(batch.quantity_remaining)) - take
        db.session.add(PharmacyDispenseLine(dispense_id=dispense.id, batch_id=batch.id, quantity=take))
        db.session.add(StockMovement(item_id=item.id, movement_type='SORTIE', quantity=take,
            reason=f'Dispensation {dispense.dispense_number} au patient {patient.patient_number}', recorded_by=current_user.id))
        remaining -= take
    db.session.add(AuditLog(user_id=current_user.id, action='DISPENSATION', entity='PharmacyDispense', entity_id=str(dispense.id), details=f'{item.code} / patient {patient.patient_number} / quantité {quantity}'))
    db.session.commit(); flash(f'Dispensation {dispense.dispense_number} enregistrée.', 'success')
    return redirect(url_for('main.pharmacy'))

@bp.get('/pharmacie/mouvements')
@login_required
def pharmacy_movements():
    movements = StockMovement.query.order_by(StockMovement.occurred_at.desc()).limit(500).all()
    return render_template('pharmacy/movements.html', movements=movements)


# Laboratoire : demandes, prélèvements, résultats et validation traçable.
@bp.get("/laboratoire")
@login_required
def laboratory():
    orders = LabOrder.query.order_by(LabOrder.requested_at.desc()).limit(300).all()
    tests = LabTest.query.filter_by(active=True).order_by(LabTest.name).all()
    patients = Patient.query.order_by(Patient.full_name).all()
    admissions_rows = Admission.query.filter_by(status="EN_COURS").order_by(Admission.admitted_at.desc()).all()
    return render_template("laboratory/index.html", orders=orders, tests=tests, patients=patients, admissions=admissions_rows)

@bp.post("/laboratoire/analyses")
@login_required
def laboratory_test_create():
    code = request.form.get("code", "").strip().upper()
    name = " ".join(request.form.get("name", "").split())
    if not code or not name:
        flash("Le code et le nom de l'analyse sont obligatoires.", "danger")
    elif LabTest.query.filter_by(code=code).first():
        flash("Ce code d'analyse existe déjà.", "warning")
    else:
        test = LabTest(code=code, name=name, specimen=request.form.get("specimen", "").strip() or None, instructions=request.form.get("instructions", "").strip() or None)
        db.session.add(test); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="AnalyseLaboratoire", entity_id=str(test.id), details=f"Ajout du test {code}"))
        db.session.commit(); flash("Analyse ajoutée au catalogue.", "success")
    return redirect(url_for("main.laboratory"))

@bp.post("/laboratoire/demandes")
@login_required
def laboratory_order_create():
    try:
        patient = db.get_or_404(Patient, int(request.form.get("patient_id", "")))
        test = db.get_or_404(LabTest, int(request.form.get("test_id", "")))
        admission_raw = request.form.get("admission_id", "").strip()
        admission = db.get_or_404(Admission, int(admission_raw)) if admission_raw else None
        if admission and admission.patient_id != patient.id: raise ValueError("Le séjour ne correspond pas au patient.")
        priority = request.form.get("priority", "NORMALE")
        if priority not in {"NORMALE", "URGENTE", "STAT"}: raise ValueError("Priorité invalide.")
    except (ValueError, TypeError) as exc:
        flash(str(exc) or "Vérifiez le patient, l'analyse et le séjour.", "danger"); return redirect(url_for("main.laboratory"))
    order = LabOrder(order_number=f"LAB-{datetime.utcnow():%Y%m%d%H%M%S%f}", patient_id=patient.id, admission_id=admission.id if admission else None, test_id=test.id, requested_by=current_user.id, priority=priority, clinical_note=request.form.get("clinical_note", "").strip() or None)
    db.session.add(order); db.session.flush()
    db.session.add(AuditLog(user_id=current_user.id, action="DEMANDE", entity="DemandeLaboratoire", entity_id=str(order.id), details=f"{order.order_number} / {patient.patient_number} / {test.code}"))
    db.session.commit(); flash(f"Demande {order.order_number} enregistrée.", "success")
    return redirect(url_for("main.laboratory"))

@bp.post("/laboratoire/demandes/<int:order_id>/prelevement")
@login_required
def laboratory_collect(order_id):
    order = db.get_or_404(LabOrder, order_id)
    if order.status != "DEMANDEE": flash("Le prélèvement a déjà été enregistré ou la demande est clôturée.", "warning")
    else:
        order.specimen_collected_at = datetime.utcnow(); order.status = "PRELEVEE"
        db.session.add(AuditLog(user_id=current_user.id, action="PRELEVEMENT", entity="DemandeLaboratoire", entity_id=str(order.id), details="Prélèvement enregistré"))
        db.session.commit(); flash("Prélèvement enregistré.", "success")
    return redirect(url_for("main.laboratory"))

@bp.route("/laboratoire/demandes/<int:order_id>/resultat", methods=["GET", "POST"])
@login_required
def laboratory_result(order_id):
    order = db.get_or_404(LabOrder, order_id)
    if request.method == "POST":
        if order.status not in {"PRELEVEE", "RESULTAT_SAISI"}:
            flash("Le résultat ne peut être saisi qu'après le prélèvement.", "danger"); return redirect(url_for("main.laboratory"))
        value = request.form.get("result_value", "").strip()
        if not value: flash("Le résultat est obligatoire.", "danger")
        elif order.result and order.result.validated_at:
            flash("Un résultat validé ne peut pas être modifié. Une procédure de rectification tracée sera nécessaire.", "warning")
        else:
            result = order.result or LabResult(order=order, entered_by=current_user.id)
            result.result_value=value; result.unit=request.form.get("unit", "").strip() or None
            result.reference_range=request.form.get("reference_range", "").strip() or None
            result.interpretation=request.form.get("interpretation", "").strip() or None
            result.entered_by=current_user.id; result.entered_at=datetime.utcnow()
            order.status="RESULTAT_SAISI"
            db.session.add(AuditLog(user_id=current_user.id, action="SAISIE_RESULTAT", entity="ResultatLaboratoire", entity_id=str(order.id), details=f"Résultat saisi pour {order.order_number}"))
            db.session.commit(); flash("Résultat enregistré en attente de validation.", "success"); return redirect(url_for("main.laboratory"))
    return render_template("laboratory/result.html", order=order)

@bp.post("/laboratoire/demandes/<int:order_id>/valider")
@login_required
def laboratory_validate(order_id):
    order = db.get_or_404(LabOrder, order_id)
    if not order.result or order.status != "RESULTAT_SAISI":
        flash("Aucun résultat en attente de validation.", "warning")
    elif order.result.entered_by == current_user.id:
        flash("La validation doit être effectuée par une autre personne habilitée que l'auteur du résultat.", "danger")
    else:
        order.result.validated_by=current_user.id; order.result.validated_at=datetime.utcnow(); order.status="VALidee".upper()
        db.session.add(AuditLog(user_id=current_user.id, action="VALIDATION_RESULTAT", entity="ResultatLaboratoire", entity_id=str(order.id), details=f"Validation de {order.order_number}"))
        db.session.commit(); flash("Résultat validé.", "success")
    return redirect(url_for("main.laboratory"))

@bp.get("/laboratoire/demandes/<int:order_id>/imprimer")
@login_required
def laboratory_print(order_id):
    order = db.get_or_404(LabOrder, order_id)
    if not order.result or not order.result.validated_at:
        flash("Le compte rendu ne peut être imprimé qu'après validation.", "warning"); return redirect(url_for("main.laboratory"))
    return render_template("laboratory/report.html", order=order)


# Consultations : données cliniques séparées du dossier administratif patient.
@bp.get("/consultations")
@login_required
def consultations():
    rows = ClinicalConsultation.query.order_by(ClinicalConsultation.consulted_at.desc()).limit(300).all()
    patients = Patient.query.order_by(Patient.full_name).all()
    admissions_rows = Admission.query.filter_by(status="EN_COURS").order_by(Admission.admitted_at.desc()).all()
    return render_template("consultations/index.html", consultations=rows, patients=patients, admissions=admissions_rows)

@bp.route("/consultations/nouvelle", methods=["GET", "POST"])
@login_required
def consultation_new():
    patients = Patient.query.order_by(Patient.full_name).all()
    admissions_rows = Admission.query.filter_by(status="EN_COURS").all()
    if request.method == "POST":
        form = request.form
        try:
            patient = db.get_or_404(Patient, int(form.get("patient_id", "")))
            admission_raw = form.get("admission_id", "").strip()
            admission = db.get_or_404(Admission, int(admission_raw)) if admission_raw else None
            if admission and admission.patient_id != patient.id:
                raise ValueError("Le séjour sélectionné ne correspond pas au patient.")
            reason = form.get("reason", "").strip()
            if not reason: raise ValueError("Le motif de consultation est obligatoire.")
            pain = form.get("pain_score", "").strip()
            if pain and not 0 <= int(pain) <= 10: raise ValueError("L'échelle de douleur doit être comprise entre 0 et 10.")
            consultation = ClinicalConsultation(consultation_number=f"CONS-{datetime.utcnow():%Y%m%d%H%M%S%f}", patient_id=patient.id, admission_id=admission.id if admission else None, clinician_id=current_user.id, reason=reason, history=form.get("history", "").strip() or None, examination=form.get("examination", "").strip() or None, diagnosis=form.get("diagnosis", "").strip() or None, care_plan=form.get("care_plan", "").strip() or None, follow_up=form.get("follow_up", "").strip() or None)
            db.session.add(consultation); db.session.flush()
            def dec_field(key):
                raw=form.get(key, "").strip().replace(",", ".")
                return Decimal(raw) if raw else None
            vitals=ConsultationVitals(consultation_id=consultation.id, temperature_c=dec_field("temperature_c"), systolic_mmhg=int(form["systolic_mmhg"]) if form.get("systolic_mmhg") else None, diastolic_mmhg=int(form["diastolic_mmhg"]) if form.get("diastolic_mmhg") else None, pulse_bpm=int(form["pulse_bpm"]) if form.get("pulse_bpm") else None, respiratory_rate=int(form["respiratory_rate"]) if form.get("respiratory_rate") else None, oxygen_percent=dec_field("oxygen_percent"), weight_kg=dec_field("weight_kg"), height_cm=dec_field("height_cm"), pain_score=int(pain) if pain else None, notes=form.get("vital_notes", "").strip() or None)
            if any([vitals.temperature_c, vitals.systolic_mmhg, vitals.diastolic_mmhg, vitals.pulse_bpm, vitals.respiratory_rate, vitals.oxygen_percent, vitals.weight_kg, vitals.height_cm, vitals.pain_score is not None, vitals.notes]): db.session.add(vitals)
            db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="ConsultationClinique", entity_id=str(consultation.id), details=f"Création {consultation.consultation_number} pour {patient.patient_number}"))
            db.session.commit(); flash("Consultation enregistrée.", "success"); return redirect(url_for("main.consultation_detail", consultation_id=consultation.id))
        except (ValueError, TypeError, InvalidOperation) as exc:
            db.session.rollback(); flash(str(exc) or "Vérifiez les valeurs saisies.", "danger")
            return render_template("consultations/form.html", patients=patients, admissions=admissions_rows, form=form)
    return render_template("consultations/form.html", patients=patients, admissions=admissions_rows, form={})

@bp.get("/consultations/<int:consultation_id>")
@login_required
def consultation_detail(consultation_id):
    consultation=db.get_or_404(ClinicalConsultation, consultation_id)
    _record_sensitive_access("CONSULTATION_DOSSIER_CLINIQUE", "Consultation", consultation.id, "Ouverture du dossier clinique")
    return render_template("consultations/detail.html", consultation=consultation)

@bp.post("/consultations/<int:consultation_id>/prescription")
@login_required
def prescription_create(consultation_id):
    consultation=db.get_or_404(ClinicalConsultation, consultation_id)
    if consultation.status == "CLOTUREE":
        flash("Cette consultation est clôturée. La prescription ne peut plus être modifiée.", "warning"); return redirect(url_for("main.consultation_detail", consultation_id=consultation.id))
    names=request.form.getlist("medicine_name[]"); dosages=request.form.getlist("dosage[]")
    if not names or not any(n.strip() for n in names) or len(names)!=len(dosages) or any(n.strip() and not d.strip() for n,d in zip(names,dosages)):
        flash("Chaque médicament doit avoir une désignation et une posologie.", "danger"); return redirect(url_for("main.consultation_detail", consultation_id=consultation.id))
    prescription=Prescription(prescription_number=f"ORD-{datetime.utcnow():%Y%m%d%H%M%S%f}", consultation_id=consultation.id, instructions=request.form.get("instructions", "").strip() or None)
    db.session.add(prescription); db.session.flush()
    for i,name in enumerate(names):
        if not name.strip(): continue
        prescription.lines.append(PrescriptionLine(medicine_name=name.strip(), dosage=dosages[i].strip(), route=(request.form.getlist("route[]")[i] or "").strip() or None, frequency=(request.form.getlist("frequency[]")[i] or "").strip() or None, duration=(request.form.getlist("duration[]")[i] or "").strip() or None, quantity=(request.form.getlist("quantity[]")[i] or "").strip() or None, directions=(request.form.getlist("directions[]")[i] or "").strip() or None))
    db.session.add(AuditLog(user_id=current_user.id, action="PRESCRIPTION", entity="Prescription", entity_id=str(prescription.id), details=prescription.prescription_number))
    db.session.commit(); flash("Prescription enregistrée. La délivrance en pharmacie reste une opération distincte.", "success")
    return redirect(url_for("main.consultation_detail", consultation_id=consultation.id))

@bp.post("/consultations/<int:consultation_id>/cloturer")
@login_required
def consultation_close(consultation_id):
    consultation=db.get_or_404(ClinicalConsultation, consultation_id)
    if not consultation.diagnosis or not consultation.care_plan:
        flash("Le diagnostic et la conduite à tenir doivent être renseignés avant clôture.", "warning")
    else:
        consultation.status="CLOTUREE"
        db.session.add(AuditLog(user_id=current_user.id, action="CLOTURE", entity="ConsultationClinique", entity_id=str(consultation.id), details="Consultation clôturée"))
        db.session.commit(); flash("Consultation clôturée.", "success")
    return redirect(url_for("main.consultation_detail", consultation_id=consultation.id))


# --- Circuit intégré : dossier permanent, facture et nouvelle visite ---
@bp.route("/patients/<int:patient_id>/nouveau-passage", methods=["GET", "POST"])
@login_required
def patient_visit_invoice(patient_id):
    """Prépare la facture d'un nouveau passage sans dupliquer le dossier patient."""
    patient = db.get_or_404(Patient, patient_id)
    items = ServiceItem.query.order_by(ServiceItem.name.asc()).all()
    if request.method == "POST":
        try:
            item = db.get_or_404(ServiceItem, int(request.form.get("service_item_id", "")))
            quantity = _money(request.form.get("quantity", "1"))
            price = _money(request.form.get("unit_price", ""))
            currency = request.form.get("currency", "CDF").upper()
            if quantity <= 0 or price <= 0 or currency not in {"CDF", "USD"}:
                raise ValueError("Quantité, tarif ou devise invalide.")
            number = f"PV-{datetime.utcnow():%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}"
            invoice = Invoice(invoice_number=number, patient_id=patient.id, admission_id=None, currency=currency, status="EMISE")
            db.session.add(invoice); db.session.flush()
            db.session.add(InvoiceLine(invoice_id=invoice.id, service_item_id=item.id,
                description_snapshot=item.name, quantity=quantity, unit_price=price))
            db.session.add(AuditLog(user_id=current_user.id, action="FACTURE_PASSAGE", entity="Facture",
                entity_id=str(invoice.id), details=f"Préfacturation du passage de {patient.patient_number}"))
            db.session.commit()
            flash("Facture du nouveau passage créée. La fiche de visite sera ouverte après paiement ou prise en charge autorisée.", "success")
            return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))
        except (ValueError, TypeError, InvalidOperation):
            db.session.rollback()
            flash("Impossible de préparer la facture. Vérifiez la prestation, le montant et la devise.", "danger")
    return render_template("reception/visit_invoice.html", patient=patient, items=items)

@bp.post("/facturation/<int:invoice_id>/prise-en-charge")
@login_required
def invoice_authorize_coverage(invoice_id):
    """Enregistre une dérogation financière explicite et traçable, après validation humaine."""
    invoice = db.get_or_404(Invoice, invoice_id)
    try:
        coverage_type = request.form.get("coverage_type", "").strip().upper()
        amount = _money(request.form.get("amount_covered", ""))
        justification = request.form.get("justification", "").strip()
        reference = request.form.get("reference", "").strip() or None
        if coverage_type not in {"ASSURANCE", "EXEMPTION", "CREDIT", "URGENCE"}:
            raise ValueError("Type de prise en charge invalide.")
        if amount <= 0 or amount > invoice.balance:
            raise ValueError("Le montant couvert doit être positif et ne pas dépasser le solde.")
        if len(justification) < 12:
            raise ValueError("Une justification détaillée est obligatoire.")
        if not user_has_permission(current_user, "billing.authorize_coverage"):
            flash("Vous n'êtes pas autorisé à valider une prise en charge.", "danger")
            return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))
        row = InvoiceCoverageAuthorization(invoice_id=invoice.id, coverage_type=coverage_type,
            amount_covered=amount, reference=reference, justification=justification,
            status="VALIDEE", authorized_by=current_user.id)
        db.session.add(row)
        db.session.add(AuditLog(user_id=current_user.id, action="PRISE_EN_CHARGE_VALIDEE", entity="Facture",
            entity_id=str(invoice.id), details=f"{coverage_type}: {amount} {invoice.currency}; {justification}"))
        db.session.commit()
        flash("Prise en charge enregistrée et tracée. Le solde financier reste visible.", "success")
    except (ValueError, TypeError, InvalidOperation) as exc:
        db.session.rollback(); flash(str(exc), "danger")
    return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))

@bp.post("/patients/<int:patient_id>/urgence/nouveau-passage")
@login_required
def emergency_visit_new(patient_id):
    """Permet l'accueil clinique urgent sans attendre le paiement préalable."""
    patient = db.get_or_404(Patient, patient_id)
    reason = request.form.get("reason", "").strip()
    if len(reason) < 12:
        flash("Décrivez brièvement le motif urgent pour assurer la traçabilité.", "danger")
        return redirect(url_for("main.patient_detail", patient_id=patient.id))
    today = date.today()
    last = db.session.query(func.max(ReceptionVisit.queue_number)).filter_by(visit_date=today).scalar() or 0
    visit = ReceptionVisit(visit_number=f"URG-{today:%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}",
        patient_id=patient.id, invoice_id=None, visit_date=today, queue_number=last+1,
        priority="URGENTE", status="EN_ATTENTE", reason="URGENCE : " + reason, registered_by=current_user.id)
    db.session.add(visit); db.session.flush()
    db.session.add(AuditLog(user_id=current_user.id, action="ACCUEIL_URGENCE_SANS_PAIEMENT_PREALABLE",
        entity="FichePassage", entity_id=str(visit.id), details=f"Patient {patient.patient_number}; motif: {reason}"))
    db.session.commit()
    flash(f"Passage urgent {visit.visit_number} créé. La prise en charge clinique n'est pas bloquée par le paiement.", "success")
    return redirect(url_for("main.reception"))

@bp.post("/facturation/<int:invoice_id>/ouvrir-passage")
@login_required
def invoice_open_visit(invoice_id):
    """Ouvre une fiche de passage après solde nul, sans dupliquer le dossier patient."""
    invoice = db.get_or_404(Invoice, invoice_id)
    if not invoice.patient_id:
        flash("Cette facture est liée à une admission et non à un nouveau passage externe.", "warning")
        return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))
    covered = sum((a.amount_covered for a in invoice.coverage_authorizations if a.status == "VALIDEE"), Decimal("0.00"))
    if invoice.balance > covered:
        flash("Le solde doit être réglé ou intégralement couvert par une autorisation validée avant l'ouverture du passage non urgent.", "warning")
        return redirect(url_for("main.invoice_detail", invoice_id=invoice.id))
    existing_visit = ReceptionVisit.query.filter_by(invoice_id=invoice.id).first()
    if existing_visit:
        flash("La fiche de passage existe déjà.", "info")
        return redirect(url_for("main.reception"))
    today = date.today()
    last = db.session.query(func.max(ReceptionVisit.queue_number)).filter_by(visit_date=today).scalar() or 0
    visit = ReceptionVisit(visit_number=f"VIS-{today:%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}",
        patient_id=invoice.patient_id, invoice_id=invoice.id, visit_date=today, queue_number=last+1,
        priority="NORMALE", status="EN_ATTENTE", reason="Nouveau passage — facture " + invoice.invoice_number,
        registered_by=current_user.id)
    invoice.status = "PAYEE"
    db.session.add(visit); db.session.flush()
    db.session.add(AuditLog(user_id=current_user.id, action="OUVERTURE_PASSAGE", entity="FichePassage",
        entity_id=str(visit.id), details=f"{visit.visit_number} ouvert après règlement de {invoice.invoice_number}"))
    db.session.commit()
    flash(f"Fiche de passage {visit.visit_number} créée. Le dossier patient permanent est conservé.", "success")
    return redirect(url_for("main.reception"))


@bp.post("/patients/<int:patient_id>/portail/inviter")
@login_required
def patient_portal_invite(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    if not user_has_permission(current_user, "patients.portal_invite") and not user_has_permission(current_user, "patients.edit"):
        flash("Autorisation insuffisante pour inviter ce patient.", "danger"); return redirect(url_for("main.patient_detail", patient_id=patient.id))
    email = (patient.email or "").strip().lower()
    if not email or "@" not in email:
        flash("Ajoutez et vérifiez d'abord une adresse e-mail dans le dossier patient.", "warning"); return redirect(url_for("main.patient_detail", patient_id=patient.id))
    account = PatientPortalAccount.query.filter_by(patient_id=patient.id).first()
    if account and account.active:
        flash("Un accès portail est déjà activé pour ce patient.", "info"); return redirect(url_for("main.patient_detail", patient_id=patient.id))
    if PatientPortalAccount.query.filter(PatientPortalAccount.email == email, PatientPortalAccount.patient_id != patient.id).first():
        flash("Cette adresse e-mail est déjà associée à un autre compte portail. Vérification manuelle nécessaire.", "danger"); return redirect(url_for("main.patient_detail", patient_id=patient.id))
    import secrets, hashlib
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    if not account: account = PatientPortalAccount(patient_id=patient.id, email=email); db.session.add(account)
    account.email=email; account.activation_token_hash=hashlib.sha256(token.encode()).hexdigest(); account.activation_expires_at=datetime.utcnow()+timedelta(hours=24); account.active=False
    db.session.add(AuditLog(user_id=current_user.id, action="INVITATION_PORTAIL_PATIENT", entity="Patient", entity_id=str(patient.id), details="Invitation d'activation envoyée")); db.session.commit()
    link = url_for("main.patient_portal_activate", token=token, _external=True)
    sent = _send_appointment_email(email, "Activation de votre espace patient — Hôpital La Providence", f"Bonjour {patient.full_name},\nUne invitation a été créée pour votre espace patient. Activez-la dans les 24 heures via ce lien :\n{link}\nSi vous n'êtes pas à l'origine de cette démarche, ignorez ce message.")
    flash("Invitation envoyée." if sent else "Invitation créée mais e-mail non envoyé. Vérifiez la configuration SMTP avant de communiquer le lien.", "success" if sent else "warning")
    return redirect(url_for("main.patient_detail", patient_id=patient.id))

@bp.route("/espace-patient/activer/<token>", methods=["GET", "POST"])
def patient_portal_activate(token):
    import hashlib
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    account=PatientPortalAccount.query.filter_by(activation_token_hash=token_hash, active=False).first()
    if not account or not account.activation_expires_at or account.activation_expires_at < datetime.utcnow():
        return render_template("patient_portal/message.html", title="Lien invalide", message="Ce lien d'activation est invalide ou expiré. Demandez une nouvelle invitation à l'accueil."), 400
    if request.method == "POST":
        password=request.form.get("password", ""); confirm=request.form.get("confirm", "")
        if len(password)<12 or password != confirm:
            flash("Choisissez un mot de passe d'au moins 12 caractères et confirmez-le.", "danger")
        else:
            account.set_password(password); account.active=True; account.activation_token_hash=None; account.activation_expires_at=None; db.session.commit()
            flash("Votre espace patient est activé. Vous pouvez vous connecter.", "success"); return redirect(url_for("main.patient_portal_login"))
    return render_template("patient_portal/activate.html", account=account)

@bp.route("/espace-patient/connexion", methods=["GET", "POST"])
def patient_portal_login():
    if request.method == "POST":
        email=request.form.get("email", "").strip().lower(); password=request.form.get("password", "")
        account=PatientPortalAccount.query.filter_by(email=email, active=True).first()
        if account and account.check_password(password):
            session["patient_portal_account_id"]=account.id; session.permanent=True; account.last_login_at=datetime.utcnow(); db.session.commit()
            return redirect(url_for("main.patient_portal_home"))
        flash("Identifiants incorrects ou espace non activé.", "danger")
    return render_template("patient_portal/login.html")

def _portal_account():
    account_id=session.get("patient_portal_account_id")
    return db.session.get(PatientPortalAccount, account_id) if account_id else None

def _portal_required():
    account=_portal_account()
    if not account or not account.active:
        session.pop("patient_portal_account_id", None); return None
    return account

@bp.get("/espace-patient")
def patient_portal_home():
    account=_portal_required()
    if not account: return redirect(url_for("main.patient_portal_login"))
    appointments=Appointment.query.filter_by(patient_id=account.patient_id).order_by(Appointment.scheduled_at.desc()).limit(100).all()
    requests=PatientAppointmentChangeRequest.query.filter_by(patient_id=account.patient_id).order_by(PatientAppointmentChangeRequest.created_at.desc()).limit(50).all()
    return render_template("patient_portal/home.html", account=account, appointments=appointments, requests=requests, now=datetime.now())

@bp.post("/espace-patient/rendez-vous/<int:appointment_id>/demande")
def patient_portal_change_request(appointment_id):
    account=_portal_required()
    if not account: return redirect(url_for("main.patient_portal_login"))
    appointment=Appointment.query.filter_by(id=appointment_id, patient_id=account.patient_id).first_or_404()
    if appointment.status != "PLANIFIE" or appointment.scheduled_at <= datetime.now():
        flash("Ce rendez-vous ne peut plus faire l'objet d'une demande en ligne.", "warning"); return redirect(url_for("main.patient_portal_home"))
    kind=request.form.get("request_type", "")
    if kind not in {"ANNULATION", "REPORT"}: flash("Type de demande invalide.", "danger"); return redirect(url_for("main.patient_portal_home"))
    if PatientAppointmentChangeRequest.query.filter_by(appointment_id=appointment.id, status="EN_ATTENTE").first():
        flash("Une demande est déjà en attente pour ce rendez-vous.", "warning"); return redirect(url_for("main.patient_portal_home"))
    requested_at=None
    if kind=="REPORT":
        try: requested_at=datetime.strptime(request.form.get("requested_at", ""), "%Y-%m-%dT%H:%M")
        except ValueError: requested_at=None
        if not requested_at or requested_at <= datetime.now(): flash("Indiquez une nouvelle date et heure dans le futur.", "danger"); return redirect(url_for("main.patient_portal_home"))
    row=PatientAppointmentChangeRequest(patient_id=account.patient_id, appointment_id=appointment.id, request_type=kind, requested_at=requested_at, reason=request.form.get("reason", "").strip()[:500] or None)
    db.session.add(row); db.session.commit()
    flash("Votre demande a été transmise à l'accueil. Le rendez-vous reste inchangé jusqu'à décision.", "success")
    return redirect(url_for("main.patient_portal_home"))

@bp.get("/espace-patient/deconnexion")
def patient_portal_logout():
    session.pop("patient_portal_account_id", None); flash("Vous êtes déconnecté de votre espace patient.", "info"); return redirect(url_for("main.patient_portal_login"))

@bp.get("/accueil/demandes-modification-rdv")
@login_required
def patient_appointment_change_requests():
    rows=PatientAppointmentChangeRequest.query.order_by(PatientAppointmentChangeRequest.created_at.desc()).limit(300).all()
    return render_template("reception/patient_change_requests.html", requests=rows)

@bp.post("/accueil/demandes-modification-rdv/<int:request_id>/decision")
@login_required
def patient_appointment_change_decision(request_id):
    row=db.get_or_404(PatientAppointmentChangeRequest, request_id)
    if row.status != "EN_ATTENTE": flash("Cette demande a déjà été traitée.", "warning"); return redirect(url_for("main.patient_appointment_change_requests"))
    decision=request.form.get("decision")
    if decision not in {"ACCEPTER", "REFUSER"}: flash("Décision invalide.", "danger"); return redirect(url_for("main.patient_appointment_change_requests"))
    appt=row.appointment
    if decision=="ACCEPTER":
        if row.request_type=="ANNULATION": appt.status="ANNULE"
        else:
            schedule=ProfessionalSchedule.query.filter_by(staff_id=appt.professional_id, weekday=row.requested_at.weekday(), active=True).first()
            error=_check_professional_slot(appt.professional_id, row.requested_at, schedule.slot_minutes if schedule else 30, exclude_appointment_id=appt.id)
            if error: flash("Report impossible : "+error, "danger"); return redirect(url_for("main.patient_appointment_change_requests"))
            appt.scheduled_at=row.requested_at
    row.status="ACCEPTEE" if decision=="ACCEPTER" else "REFUSEE"; row.decision_note=request.form.get("decision_note", "").strip()[:500] or None; row.decided_by=current_user.id; row.decided_at=datetime.utcnow()
    db.session.add(AuditLog(user_id=current_user.id, action="DECISION_DEMANDE_RDV_PATIENT", entity="RendezVous", entity_id=str(appt.id), details=f"Demande {row.request_type} : {row.status}")); db.session.commit()
    _send_appointment_email(row.patient.email or "", "Mise à jour de votre rendez-vous — Hôpital La Providence", f"Bonjour {row.patient.full_name},\nVotre demande de {row.request_type.lower()} concernant {appt.appointment_number} a été {row.status.lower()}.\n"+(f"Nouvelle date : {appt.scheduled_at:%d/%m/%Y à %H:%M}.\n" if row.status=="ACCEPTEE" and row.request_type=="REPORT" else "")+f"Note : {row.decision_note or 'Aucune'}. Contactez l'accueil pour toute question.")
    flash("Décision enregistrée.", "success"); return redirect(url_for("main.patient_appointment_change_requests"))


@bp.get("/accueil/notifications-rendez-vous")
@login_required
def appointment_notifications():
    rows = AppointmentNotification.query.order_by(AppointmentNotification.created_at.desc()).limit(300).all()
    return render_template("reception/appointment_notifications.html", notifications=rows)


def _send_appointment_email(recipient, subject, body):
    import os, smtplib
    from email.message import EmailMessage
    host=os.getenv("MAIL_SERVER"); user=os.getenv("MAIL_USERNAME")
    sender=os.getenv("MAIL_DEFAULT_SENDER") or user
    if not host or not sender: return False
    msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=sender; msg["To"]=recipient; msg.set_content(body)
    try:
        port=int(os.getenv("MAIL_PORT","587"))
        if os.getenv("MAIL_USE_SSL","false").lower()=="true":
            with smtplib.SMTP_SSL(host,port,timeout=15) as smtp:
                if user: smtp.login(user,os.getenv("MAIL_PASSWORD",""))
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host,port,timeout=15) as smtp:
                smtp.starttls()
                if user: smtp.login(user,os.getenv("MAIL_PASSWORD",""))
                smtp.send_message(msg)
        return True
    except Exception: return False


@bp.route("/demande-rendez-vous", methods=["GET","POST"])
def online_appointment_request():
    services=HospitalService.query.order_by(HospitalService.name.asc()).all()
    if request.method=="POST":
        try:
            name=" ".join(request.form.get("full_name","").split())
            email=request.form.get("email","").strip().lower()
            phone=request.form.get("phone","").strip()
            wanted=datetime.strptime(request.form.get("preferred_date",""),"%Y-%m-%d").date()
            sid=request.form.get("service_id","").strip()
            service=db.get_or_404(HospitalService,int(sid)) if sid else None
            period=request.form.get("preferred_period","INDIFFERENT")
            if len(name)<3 or "@" not in email or len(phone)<6 or wanted<date.today() or period not in {"MATIN","APRES_MIDI","INDIFFERENT"}: raise ValueError()
            row=OnlineAppointmentRequest(request_number=f"DR-{datetime.utcnow():%y%m%d%H%M%S}",full_name=name,email=email,phone=phone,service_id=service.id if service else None,preferred_date=wanted,preferred_period=period,reason=request.form.get("reason","").strip()[:500] or None)
            db.session.add(row); db.session.commit()
            flash("Demande transmise. Elle n'est pas encore confirmée ; l'accueil vérifiera les disponibilités.","success")
            return redirect(url_for("main.online_appointment_request"))
        except (ValueError,TypeError):
            db.session.rollback(); flash("Vérifiez les coordonnées et la date souhaitée.","danger")
    return render_template("public/appointment_request.html",services=services,today_iso=date.today().isoformat())


@bp.get("/accueil/demandes-rendez-vous")
@login_required
def online_appointment_requests():
    status=request.args.get("status","EN_ATTENTE"); term=request.args.get("q","").strip()
    q=OnlineAppointmentRequest.query
    if status in {"EN_ATTENTE","ACCEPTEE","REFUSEE"}: q=q.filter_by(status=status)
    if term: q=q.filter(or_(OnlineAppointmentRequest.request_number.ilike(f"%{term}%"),OnlineAppointmentRequest.full_name.ilike(f"%{term}%"),OnlineAppointmentRequest.email.ilike(f"%{term}%"),OnlineAppointmentRequest.phone.ilike(f"%{term}%")))
    rows=q.order_by(OnlineAppointmentRequest.created_at.desc()).limit(300).all()
    return render_template("reception/online_requests.html",requests=rows,status=status,search=term,professionals=StaffProfile.query.filter_by(status="ACTIF").order_by(StaffProfile.full_name.asc()).all())


def _check_professional_slot(staff_id, starts_at, minutes=30, exclude_appointment_id=None):
    staff = db.session.get(StaffProfile, int(staff_id)) if staff_id else None
    if not staff or staff.status != "ACTIF":
        return "Sélectionnez un professionnel actif."
    schedule = ProfessionalSchedule.query.filter_by(staff_id=staff.id, weekday=starts_at.weekday(), active=True).first()
    if not schedule:
        return "Aucun horaire de consultation n'est défini pour ce professionnel ce jour-là."
    end_time = (datetime.combine(starts_at.date(), starts_at.time()) + timedelta(minutes=minutes)).time()
    if starts_at.time() < schedule.start_time or end_time > schedule.end_time:
        return "Le créneau est en dehors des horaires du professionnel."
    leave = StaffLeaveRequest.query.filter_by(staff_id=staff.id, status="APPROUVEE").filter(
        StaffLeaveRequest.start_date <= starts_at.date(), StaffLeaveRequest.end_date >= starts_at.date()).first()
    if leave:
        return "Le professionnel est en congé approuvé à cette date."
    end_at = starts_at + timedelta(minutes=minutes)
    overlap_query = Appointment.query.filter_by(professional_id=staff.id, status="PLANIFIE").filter(
        Appointment.scheduled_at < end_at,
        Appointment.scheduled_at > starts_at - timedelta(minutes=minutes))
    if exclude_appointment_id: overlap_query = overlap_query.filter(Appointment.id != exclude_appointment_id)
    overlap = overlap_query.first()
    if overlap:
        return "Ce professionnel a déjà un rendez-vous sur ce créneau."
    return None


@bp.post("/accueil/demandes-rendez-vous/<int:request_id>/decision")
@login_required
def online_appointment_decision(request_id):
    row=db.get_or_404(OnlineAppointmentRequest,request_id)
    if row.status!="EN_ATTENTE":
        flash("Demande déjà traitée.","warning"); return redirect(url_for("main.online_appointment_requests"))
    if request.form.get("decision")=="ACCEPTER":
        try:
            at=datetime.strptime(request.form.get("scheduled_at",""),"%Y-%m-%dT%H:%M")
            professional_id=int(request.form.get("professional_id",""))
            if at<=datetime.now(): raise ValueError("La date doit être future.")
            schedule=ProfessionalSchedule.query.filter_by(staff_id=professional_id,weekday=at.weekday(),active=True).first()
            if not schedule: raise ValueError("Aucun horaire configuré pour ce professionnel à cette date.")
            slot_error=_check_professional_slot(professional_id,at,schedule.slot_minutes)
            if slot_error: raise ValueError(slot_error)
            patient=Patient.query.filter(or_(Patient.email.ilike(row.email),Patient.phone==row.phone)).first()
            if patient is None:
                patient=Patient(patient_number=f"PAT-{datetime.utcnow():%y%m%d%H%M%S}",full_name=row.full_name,email=row.email,phone=row.phone)
                db.session.add(patient); db.session.flush()
            appt=Appointment(appointment_number=f"RDV-{at:%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}",patient_id=patient.id,service_id=row.service_id,professional_id=professional_id,scheduled_at=at,reason="Demande en ligne — "+(row.reason or "Consultation"),status="PLANIFIE",created_by=current_user.id)
            db.session.add(appt); row.patient_id=patient.id; row.appointment=appt; row.proposed_at=at
            row.status="ACCEPTEE"; row.decided_by=current_user.id; row.decided_at=datetime.utcnow()
            db.session.add(AuditLog(user_id=current_user.id,action="ACCEPTATION_DEMANDE_RDV",entity="DemandeRendezVous",entity_id=str(row.id),details=f"Demande {row.request_number} acceptée"))
            db.session.commit()
            body=f"Bonjour {row.full_name},\\nVotre demande est acceptée.\\nRéférence : {row.request_number}\\nService : {row.service.name if row.service else 'Consultation'}\\nDate : {at:%d/%m/%Y}\\nHeure : {at:%H:%M}\\nPrésentez-vous 15 minutes avant.\\nHôpital La Providence."
            sent=_send_appointment_email(row.email,"Confirmation de rendez-vous — Hôpital La Providence",body)
            flash("Rendez-vous enregistré. "+("Courriel envoyé." if sent else "Courriel non envoyé : configurez le SMTP."),"success" if sent else "warning")
        except (ValueError,TypeError) as exc:
            db.session.rollback(); flash(str(exc) or "Créneau invalide.","danger")
    elif request.form.get("decision")=="REFUSER":
        row.status="REFUSEE"; row.decided_by=current_user.id; row.decided_at=datetime.utcnow()
        row.decision_note=request.form.get("decision_note","").strip()[:500] or None
        db.session.add(AuditLog(user_id=current_user.id,action="REFUS_DEMANDE_RDV",entity="DemandeRendezVous",entity_id=str(row.id),details=f"Demande {row.request_number} refusée"))
        db.session.commit()
        sent=_send_appointment_email(row.email,"Réponse à votre demande — Hôpital La Providence",f"Bonjour {row.full_name}, nous ne pouvons confirmer ce créneau. Contactez l'accueil pour une autre date.")
        flash("Demande refusée."+(" Courriel envoyé." if sent else " SMTP à configurer."),"success" if sent else "warning")
    return redirect(url_for("main.online_appointment_requests"))


@bp.get("/api/consultation-slots")
@login_required
def consultation_available_slots():
    raw_date=request.args.get("date","")
    raw_staff=request.args.get("professional_id","")
    try:
        day=datetime.strptime(raw_date,"%Y-%m-%d").date()
        staff_id=int(raw_staff)
    except (ValueError,TypeError):
        return jsonify({"slots":[],"message":"Date ou professionnel invalide."}),400
    staff=db.session.get(StaffProfile,staff_id)
    if not staff or staff.status!="ACTIF":
        return jsonify({"slots":[],"message":"Professionnel indisponible."}),404
    if day<date.today():
        return jsonify({"slots":[],"message":"La date est passée."})
    leave=StaffLeaveRequest.query.filter_by(staff_id=staff_id,status="APPROUVEE").filter(
        StaffLeaveRequest.start_date<=day,StaffLeaveRequest.end_date>=day).first()
    if leave:
        return jsonify({"slots":[],"message":"Professionnel en congé."})
    schedule=ProfessionalSchedule.query.filter_by(staff_id=staff_id,weekday=day.weekday(),active=True).first()
    if not schedule:
        return jsonify({"slots":[],"message":"Aucun horaire configuré pour ce jour."})
    duration=schedule.slot_minutes
    start=datetime.combine(day,schedule.start_time)
    finish=datetime.combine(day,schedule.end_time)
    now=datetime.now()
    slots=[]
    cursor=start
    while cursor+timedelta(minutes=duration)<=finish:
        end=cursor+timedelta(minutes=duration)
        if cursor>now:
            conflict=Appointment.query.filter_by(professional_id=staff_id,status="PLANIFIE").filter(
                Appointment.scheduled_at<end,
                Appointment.scheduled_at>cursor-timedelta(minutes=duration)).first()
            if not conflict:
                slots.append({"value":cursor.strftime("%Y-%m-%dT%H:%M"),"label":cursor.strftime("%H:%M")})
        cursor=end
    return jsonify({"slots":slots,"duration":duration,"message":"Créneaux disponibles." if slots else "Aucun créneau libre pour cette date."})


@bp.get("/consultations/agenda-professionnels")
@login_required
def professional_agenda():
    raw=request.args.get("date") or date.today().isoformat()
    try: day=datetime.strptime(raw,"%Y-%m-%d").date()
    except ValueError: day=date.today()
    staff_id=request.args.get("professional_id","").strip()
    q=Appointment.query.filter(Appointment.scheduled_at>=datetime.combine(day,datetime.min.time()),
        Appointment.scheduled_at<datetime.combine(day+timedelta(days=1),datetime.min.time()))
    if staff_id.isdigit(): q=q.filter(Appointment.professional_id==int(staff_id))
    appointments=q.order_by(Appointment.scheduled_at.asc()).all()
    professionals=StaffProfile.query.filter_by(status="ACTIF").order_by(StaffProfile.full_name.asc()).all()
    return render_template("reception/professional_agenda.html",appointments=appointments,professionals=professionals,selected_date=day,selected_professional=staff_id)


@bp.route("/rh/horaires-consultation",methods=["GET","POST"])
@login_required
def professional_schedules():
    professionals=StaffProfile.query.filter_by(status="ACTIF").order_by(StaffProfile.full_name.asc()).all()
    if request.method=="POST":
        try:
            staff_id=int(request.form["staff_id"]); weekday=int(request.form["weekday"])
            start=datetime.strptime(request.form["start_time"],"%H:%M").time()
            end=datetime.strptime(request.form["end_time"],"%H:%M").time()
            duration=int(request.form.get("slot_minutes","30"))
            if weekday not in range(7) or start>=end or duration not in (15,20,30,45,60,90): raise ValueError()
            row=ProfessionalSchedule.query.filter_by(staff_id=staff_id,weekday=weekday).first()
            if row is None: row=ProfessionalSchedule(staff_id=staff_id,weekday=weekday); db.session.add(row)
            row.start_time=start; row.end_time=end; row.slot_minutes=duration; row.active=True
            db.session.commit(); flash("Horaire enregistré.","success")
        except (ValueError,KeyError,TypeError):
            db.session.rollback(); flash("Horaire invalide. Vérifiez les champs.","danger")
    schedules=ProfessionalSchedule.query.order_by(ProfessionalSchedule.weekday.asc()).all()
    return render_template("reception/professional_schedules.html",professionals=professionals,schedules=schedules)


# --- Accueil, rendez-vous et triage ---
@bp.get("/accueil")
@login_required
def reception():
    today = date.today()
    visits = ReceptionVisit.query.filter_by(visit_date=today).order_by(ReceptionVisit.queue_number.asc()).all()
    appointments = Appointment.query.filter(Appointment.scheduled_at >= datetime.combine(today, datetime.min.time()), Appointment.scheduled_at < datetime.combine(today, datetime.max.time())).order_by(Appointment.scheduled_at.asc()).all()
    waiting = ReceptionVisit.query.filter_by(visit_date=today, status="EN_ATTENTE").count()
    return render_template("reception/index.html", visits=visits, appointments=appointments, waiting=waiting, today=today, patients=Patient.query.order_by(Patient.full_name.asc()).all(), services=HospitalService.query.order_by(HospitalService.name.asc()).all())

@bp.route("/accueil/rendez-vous", methods=["GET", "POST"])
@login_required
def appointment_new():
    patients = Patient.query.order_by(Patient.full_name.asc()).all()
    services = HospitalService.query.order_by(HospitalService.name.asc()).all()
    if request.method == "POST":
        try:
            patient = db.get_or_404(Patient, int(request.form.get("patient_id", "")))
            scheduled = datetime.strptime(request.form.get("scheduled_at", ""), "%Y-%m-%dT%H:%M")
            service_raw = request.form.get("service_id", "").strip()
            service = db.get_or_404(HospitalService, int(service_raw)) if service_raw else None
            if scheduled < datetime.now() - timedelta(minutes=1):
                raise ValueError("La date du rendez-vous ne peut pas être dans le passé.")
            code = f"RDV-{scheduled:%y%m%d}-{int(datetime.utcnow().timestamp())%1000000:06d}"
            row = Appointment(appointment_number=code, patient_id=patient.id, service_id=service.id if service else None,
                scheduled_at=scheduled, reason=request.form.get("reason", "").strip() or None, created_by=current_user.id)
            db.session.add(row); db.session.flush()
            db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="RendezVous", entity_id=str(row.id), details=f"Rendez-vous {code}"))
            db.session.commit(); flash("Rendez-vous enregistré.", "success"); return redirect(url_for("main.reception"))
        except (ValueError, TypeError):
            db.session.rollback(); flash("Rendez-vous invalide. Vérifiez le patient, le service et la date.", "danger")
    return render_template("reception/appointment_form.html", patients=patients, services=services)

@bp.post("/accueil/rendez-vous/<int:appointment_id>/annuler")
@login_required
def appointment_cancel(appointment_id):
    row = db.get_or_404(Appointment, appointment_id)
    if row.status != "PLANIFIE":
        flash("Seul un rendez-vous planifié peut être annulé.", "warning")
    else:
        row.status = "ANNULE"
        db.session.add(AuditLog(user_id=current_user.id, action="ANNULATION", entity="RendezVous", entity_id=str(row.id), details=f"Annulation {row.appointment_number}"))
        db.session.commit(); flash("Rendez-vous annulé.", "success")
    return redirect(url_for("main.reception"))

@bp.post("/accueil/arrivee")
@login_required
def reception_checkin():
    flash("Pour créer un nouveau passage, ouvrez le dossier permanent du patient, préparez sa facture et enregistrez le paiement. La fiche de passage sera ensuite générée automatiquement.", "info")
    return redirect(url_for("main.reception"))

@bp.post("/accueil/visite/<int:visit_id>/triage")
@login_required
def reception_triage(visit_id):
    visit = db.get_or_404(ReceptionVisit, visit_id)
    if visit.triage:
        flash("Le triage de cette arrivée est déjà enregistré. Une correction doit être tracée.", "warning")
        return redirect(url_for("main.reception"))
    try:
        def optional_decimal(key, places=1):
            raw=request.form.get(key, "").strip()
            if not raw: return None
            value=Decimal(raw.replace(",", "."))
            if not value.is_finite() or value < 0: raise ValueError
            return value
        def optional_int(key, low=0, high=300):
            raw=request.form.get(key, "").strip()
            if not raw: return None
            value=int(raw)
            if not low <= value <= high: raise ValueError
            return value
        temperature=optional_decimal("temperature_c")
        oxygen=optional_decimal("oxygen_percent")
        if temperature is not None and temperature > 50: raise ValueError
        if oxygen is not None and oxygen > 100: raise ValueError
        pain=optional_int("pain_score",0,10)
        row=TriageAssessment(visit_id=visit.id, temperature_c=temperature, systolic_mmhg=optional_int("systolic_mmhg"),
            diastolic_mmhg=optional_int("diastolic_mmhg"), pulse_bpm=optional_int("pulse_bpm"),
            respiratory_rate=optional_int("respiratory_rate"), oxygen_percent=oxygen,
            weight_kg=optional_decimal("weight_kg"), height_cm=optional_decimal("height_cm"), pain_score=pain,
            danger_signs=request.form.get("danger_signs", "").strip() or None,
            observations=request.form.get("observations", "").strip() or None, assessed_by=current_user.id)
        db.session.add(row); visit.status="TRIE"
        if row.danger_signs: visit.priority="URGENTE" if visit.priority == "NORMALE" else visit.priority
        db.session.add(AuditLog(user_id=current_user.id, action="TRIAGE", entity="Accueil", entity_id=str(visit.id), details="Constantes et observations de triage enregistrées"))
        db.session.commit(); flash("Triage enregistré.", "success")
    except (ValueError, InvalidOperation, TypeError):
        db.session.rollback(); flash("Valeurs de triage invalides. Vérifiez les unités et les plages autorisées.", "danger")
    return redirect(url_for("main.reception"))

@bp.post("/accueil/visite/<int:visit_id>/orienter")
@login_required
def reception_orient(visit_id):
    visit=db.get_or_404(ReceptionVisit, visit_id)
    target=request.form.get("status", "")
    if target not in {"ORIENTE", "TERMINE"}:
        flash("Orientation invalide.", "danger")
    elif visit.status == "TERMINE":
        flash("Cette arrivée est déjà clôturée.", "warning")
    else:
        visit.status=target
        db.session.add(AuditLog(user_id=current_user.id, action="ORIENTATION", entity="Accueil", entity_id=str(visit.id), details=f"Statut {target}"))
        db.session.commit(); flash("Orientation mise à jour.", "success")
    return redirect(url_for("main.reception"))


# --- Administration des comptes, rôles et autorisations ---
@bp.get("/administration/personnel")
@login_required
def staff_admin():
    if not user_has_permission(current_user, "staff.manage"):
        flash("Vous ne disposez pas de l'autorisation de gérer le personnel.", "danger")
        return redirect(url_for("main.dashboard"))
    users = User.query.order_by(User.full_name.asc()).all()
    roles = Role.query.order_by(Role.name.asc()).all()
    return render_template("admin/staff.html", users=users, roles=roles)

@bp.route("/administration/personnel/nouveau", methods=["GET", "POST"])
@login_required
def staff_new():
    if not user_has_permission(current_user, "staff.manage"):
        flash("Accès non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    roles = Role.query.order_by(Role.name.asc()).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        full_name = " ".join(request.form.get("full_name", "").split())
        password = request.form.get("password", "")
        errors=[]
        if not username or not full_name: errors.append("Identifiant et nom complet obligatoires.")
        if User.query.filter(func.lower(User.username)==username).first(): errors.append("Cet identifiant existe déjà.")
        if len(password) < 12: errors.append("Le mot de passe initial doit contenir au moins 12 caractères.")
        selected=[]
        for raw in request.form.getlist("role_ids"):
            try:
                role=db.session.get(Role,int(raw))
                if role: selected.append(role)
            except (ValueError,TypeError): pass
        if not selected: errors.append("Attribuez au moins un rôle au compte.")
        if errors:
            for error in errors: flash(error,"danger")
            return render_template("admin/staff_form.html", roles=roles, form=request.form)
        user=User(username=username,full_name=full_name,active=True); user.set_password(password); user.roles=selected
        db.session.add(user); db.session.flush()
        db.session.add(AuditLog(user_id=current_user.id,action="CREATION_COMPTE",entity="Utilisateur",entity_id=str(user.id),details=f"Création du compte {username} et attribution des rôles"))
        db.session.commit(); flash("Compte utilisateur créé. Remettez les identifiants au titulaire par un canal sécurisé.","success")
        return redirect(url_for("main.staff_admin"))
    return render_template("admin/staff_form.html", roles=roles, form={})

@bp.route("/administration/personnel/<int:user_id>/modifier", methods=["GET", "POST"])
@login_required
def staff_edit(user_id):
    if not user_has_permission(current_user, "staff.manage"):
        flash("Accès non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    user=db.get_or_404(User,user_id); roles=Role.query.order_by(Role.name.asc()).all()
    if request.method == "POST":
        full_name=" ".join(request.form.get("full_name", "").split())
        if not full_name:
            flash("Le nom complet est obligatoire.","danger")
        else:
            user.full_name=full_name
            user.active=(request.form.get("active")=="1")
            if user.id==current_user.id and not user.active:
                user.active=True; flash("Vous ne pouvez pas désactiver votre propre compte.","warning")
            selected=[]
            for raw in request.form.getlist("role_ids"):
                try:
                    role=db.session.get(Role,int(raw))
                    if role: selected.append(role)
                except (ValueError,TypeError): pass
            if selected: user.roles=selected
            new_password=request.form.get("new_password","")
            if new_password:
                if len(new_password)<12: flash("Le nouveau mot de passe doit contenir au moins 12 caractères.","danger"); return render_template("admin/staff_form.html",roles=roles,form=request.form,user=user)
                user.set_password(new_password)
            db.session.add(AuditLog(user_id=current_user.id,action="MODIFICATION_COMPTE",entity="Utilisateur",entity_id=str(user.id),details="Modification du compte et de ses rôles"))
            db.session.commit(); flash("Compte mis à jour.","success"); return redirect(url_for("main.staff_admin"))
    form={"full_name":user.full_name,"active":"1" if user.active else "0","role_ids":[str(r.id) for r in user.roles]}
    return render_template("admin/staff_form.html",roles=roles,form=form,user=user)

@bp.route("/administration/roles", methods=["GET", "POST"])
@login_required
def roles_admin():
    if not user_has_permission(current_user, "staff.manage"):
        flash("Accès non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    roles=Role.query.order_by(Role.name.asc()).all()
    permissions=Permission.query.order_by(Permission.code.asc()).all()
    if request.method=="POST":
        name=" ".join(request.form.get("name","").split()).lower().replace(" ","_")
        if not name: flash("Le nom du rôle est obligatoire.","danger")
        elif Role.query.filter_by(name=name).first(): flash("Ce rôle existe déjà.","warning")
        else:
            role=Role(name=name); db.session.add(role); db.session.flush()
            chosen=[]
            for code in request.form.getlist("permissions"):
                permission=Permission.query.filter_by(code=code).first()
                if permission: chosen.append(permission)
            role.permissions=chosen
            db.session.add(AuditLog(user_id=current_user.id,action="CREATION_ROLE",entity="Role",entity_id=str(role.id),details=f"Création du rôle {name}"))
            db.session.commit(); flash("Rôle créé avec ses autorisations.","success"); return redirect(url_for("main.roles_admin"))
    return render_template("admin/roles.html",roles=roles,permissions=permissions,catalog=PERMISSION_CATALOG)

@bp.post("/administration/roles/initialiser-autorisations")
@login_required
def permissions_seed():
    if not user_has_permission(current_user, "staff.manage"):
        flash("Accès non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    created=0
    for code,description in PERMISSION_CATALOG.items():
        if not Permission.query.filter_by(code=code).first():
            db.session.add(Permission(code=code,description=description)); created+=1
    db.session.add(AuditLog(user_id=current_user.id,action="INITIALISATION_AUTORISATIONS",entity="Permission",details=f"{created} autorisation(s) ajoutée(s) au catalogue"))
    db.session.commit(); flash(f"Catalogue actualisé : {created} nouvelle(s) autorisation(s).", "success")
    return redirect(url_for("main.roles_admin"))

@bp.get("/administration/journal")
@login_required
def audit_admin():
    if not user_has_permission(current_user, "audit.view"):
        flash("Vous ne disposez pas de l'autorisation de consulter le journal.","danger"); return redirect(url_for("main.dashboard"))
    logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(500).all()
    return render_template("admin/audit.html",logs=logs)


# Ressources humaines : dossiers du personnel, présences et congés.
@bp.get("/rh/personnel")
@login_required
def hr_staff_list():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    staff = StaffProfile.query.order_by(StaffProfile.full_name.asc()).all()
    return render_template("hr/staff.html", staff=staff)

@bp.route("/rh/personnel/nouveau", methods=["GET", "POST"])
@login_required
def hr_staff_new():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        f=request.form; name=" ".join(f.get("full_name","").split()); title=f.get("job_title","").strip()
        if not name or not title:
            flash("Le nom et la fonction sont obligatoires.", "danger")
        else:
            hired=None
            try: hired=datetime.strptime(f.get("hired_on"), "%Y-%m-%d").date() if f.get("hired_on") else None
            except ValueError: flash("Date d'engagement invalide.", "danger"); return render_template("hr/staff_form.html", form=f)
            profile=StaffProfile(employee_number=f"TEMP-{uuid4().hex}", full_name=name, job_title=title, department=f.get("department") or None, contract_type=f.get("contract_type") or None, contract_reference=f.get("contract_reference") or None, hired_on=hired, phone=f.get("phone") or None, email=f.get("email") or None, status=f.get("status") or "ACTIF")
            db.session.add(profile); db.session.flush(); profile.employee_number=f"HLP-RH-{datetime.utcnow().year}-{profile.id:06d}"; db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="Personnel", entity_id=str(profile.id), details="Création du dossier RH")); db.session.commit()
            flash("Dossier du personnel créé. Sa carte de service est disponible immédiatement.", "success"); return redirect(url_for("main.staff_card", staff_id=profile.id))
        return render_template("hr/staff_form.html", form=f)
    return render_template("hr/staff_form.html", form={})

@bp.get("/rh/presences")
@login_required
def hr_attendance():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    staff=StaffProfile.query.filter_by(status="ACTIF").order_by(StaffProfile.full_name).all()
    records=StaffAttendance.query.order_by(StaffAttendance.work_date.desc()).limit(250).all()
    return render_template("hr/attendance.html", staff=staff, records=records, today=date.today())

@bp.post("/rh/presences/enregistrer")
@login_required
def hr_attendance_save():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    f=request.form
    try:
        staff_id=int(f.get("staff_id")); work_date=datetime.strptime(f.get("work_date"), "%Y-%m-%d").date()
        profile=db.get_or_404(StaffProfile, staff_id)
        check_in=datetime.strptime(f.get("check_in"), "%H:%M").time() if f.get("check_in") else None
        check_out=datetime.strptime(f.get("check_out"), "%H:%M").time() if f.get("check_out") else None
    except (ValueError, TypeError):
        flash("Vérifiez le personnel, la date et les heures.", "danger"); return redirect(url_for("main.hr_attendance"))
    record=StaffAttendance.query.filter_by(staff_id=profile.id, work_date=work_date).first()
    if record is None: record=StaffAttendance(staff_id=profile.id, work_date=work_date, recorded_by=current_user.id); db.session.add(record)
    record.shift_label=f.get("shift_label") or None; record.check_in=check_in; record.check_out=check_out; record.status=f.get("status") or "PRESENT"; record.note=f.get("note") or None
    db.session.add(AuditLog(user_id=current_user.id, action="ENREGISTREMENT", entity="Presence", entity_id=str(record.id or "nouveau"), details=f"Présence {profile.employee_number} du {work_date.isoformat()}")); db.session.commit()
    flash("Présence enregistrée.", "success"); return redirect(url_for("main.hr_attendance"))

@bp.get("/rh/conges")
@login_required
def hr_leaves():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    staff=StaffProfile.query.order_by(StaffProfile.full_name).all(); requests=StaffLeaveRequest.query.order_by(StaffLeaveRequest.requested_at.desc()).all()
    return render_template("hr/leaves.html", staff=staff, requests=requests)

@bp.post("/rh/conges/nouveau")
@login_required
def hr_leave_new():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    f=request.form
    try:
        staff=db.get_or_404(StaffProfile, int(f.get("staff_id"))); start=datetime.strptime(f.get("start_date"), "%Y-%m-%d").date(); end=datetime.strptime(f.get("end_date"), "%Y-%m-%d").date()
        if end < start: raise ValueError()
    except (ValueError, TypeError):
        flash("Sélectionnez un personnel et une période de congé valide.", "danger"); return redirect(url_for("main.hr_leaves"))
    item=StaffLeaveRequest(staff_id=staff.id, leave_type=f.get("leave_type") or "ANNUEL", start_date=start, end_date=end, reason=f.get("reason") or None)
    db.session.add(item); db.session.flush(); db.session.add(AuditLog(user_id=current_user.id, action="DEMANDE", entity="Conge", entity_id=str(item.id), details=f"Demande de congé {staff.employee_number}")); db.session.commit()
    flash("Demande de congé enregistrée en attente de validation.", "success"); return redirect(url_for("main.hr_leaves"))

@bp.post("/rh/conges/<int:leave_id>/decision")
@login_required
def hr_leave_decision(leave_id):
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    item=db.get_or_404(StaffLeaveRequest, leave_id); decision=request.form.get("decision")
    if decision not in {"APPROUVE", "REFUSE"} or item.status != "EN_ATTENTE":
        flash("Décision invalide ou demande déjà traitée.", "danger")
    else:
        item.status=decision; item.reviewed_by=current_user.id; item.reviewed_at=datetime.utcnow(); db.session.add(AuditLog(user_id=current_user.id, action=decision, entity="Conge", entity_id=str(item.id), details="Décision sur demande de congé")); db.session.commit(); flash("Décision enregistrée.", "success")
    return redirect(url_for("main.hr_leaves"))


@bp.get("/patients/<int:patient_id>/carte")
@login_required
def patient_card(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    return render_template("cards/patient.html", patient=patient)

@bp.get("/rh/personnel/<int:staff_id>/carte")
@login_required
def staff_card(staff_id):
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    staff = db.get_or_404(StaffProfile, staff_id)
    return render_template("cards/staff.html", staff=staff)

@bp.get("/rh/paie")
@login_required
def payroll_index():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    records = PayrollRecord.query.order_by(PayrollRecord.period.desc(), PayrollRecord.id.desc()).limit(300).all()
    staff = StaffProfile.query.filter_by(status="ACTIF").order_by(StaffProfile.full_name).all()
    components = PayrollComponent.query.filter_by(active=True).order_by(PayrollComponent.name).all()
    return render_template("hr/payroll.html", records=records, staff=staff, components=components)

@bp.post("/rh/paie/rubrique")
@login_required
def payroll_component_new():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    name=request.form.get("name", "").strip(); kind=request.form.get("component_type")
    if not name or kind not in {"GAIN", "RETENUE"}: flash("Nom et type de rubrique obligatoires.", "danger")
    elif PayrollComponent.query.filter_by(name=name).first(): flash("Cette rubrique existe déjà.", "warning")
    else:
        db.session.add(PayrollComponent(name=name, component_type=kind)); db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="RubriquePaie", details=name)); db.session.commit(); flash("Rubrique ajoutée.", "success")
    return redirect(url_for("main.payroll_index"))

@bp.post("/rh/paie/nouveau")
@login_required
def payroll_new():
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    f=request.form
    try:
        staff=db.get_or_404(StaffProfile, int(f.get("staff_id"))); period=f.get("period", ""); datetime.strptime(period+"-01", "%Y-%m-%d")
        base=Decimal(f.get("base_amount", "")); currency=f.get("currency", "CDF").upper()
        if base < 0 or currency not in {"CDF", "USD", "EUR"}: raise ValueError()
        if PayrollRecord.query.filter_by(staff_id=staff.id, period=period).first(): raise ValueError("duplicate")
    except Exception as exc:
        flash("Vérifiez le personnel, la période, le montant et la devise. Une paie existe peut-être déjà pour ce mois.", "danger"); return redirect(url_for("main.payroll_index"))
    record=PayrollRecord(staff_id=staff.id, period=period, base_amount=base, currency=currency, created_by=current_user.id)
    db.session.add(record); db.session.flush()
    for component in PayrollComponent.query.filter_by(active=True).all():
        raw=f.get("component_"+str(component.id), "0").strip() or "0"
        try: amount=Decimal(raw)
        except InvalidOperation: amount=Decimal("-1")
        if amount < 0: db.session.rollback(); flash("Montant de rubrique invalide.", "danger"); return redirect(url_for("main.payroll_index"))
        if amount: db.session.add(PayrollLine(payroll_id=record.id, component_id=component.id, amount=amount))
    db.session.add(AuditLog(user_id=current_user.id, action="CREATION", entity="Paie", entity_id=str(record.id), details=f"Paie {staff.employee_number}, période {period}")); db.session.commit()
    flash("Bulletin de paie préparé. Vérifiez-le avant validation et paiement.", "success"); return redirect(url_for("main.payroll_slip", payroll_id=record.id))

@bp.get("/rh/paie/<int:payroll_id>/bulletin")
@login_required
def payroll_slip(payroll_id):
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    record=db.get_or_404(PayrollRecord, payroll_id)
    return render_template("hr/payroll_slip.html", record=record)

@bp.post("/rh/paie/<int:payroll_id>/statut")
@login_required
def payroll_status(payroll_id):
    if not user_has_permission(current_user, "hr.manage"):
        flash("Accès RH non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    record=db.get_or_404(PayrollRecord, payroll_id); status=request.form.get("status")
    if status not in {"BROUILLON", "VALIDE", "PAYE"} or (record.status == "PAYE" and status != "PAYE"):
        flash("Transition de statut non autorisée.", "danger")
    else:
        record.status=status; db.session.add(AuditLog(user_id=current_user.id, action="STATUT_"+status, entity="Paie", entity_id=str(record.id), details="Changement du statut du bulletin")); db.session.commit(); flash("Statut du bulletin mis à jour.", "success")
    return redirect(url_for("main.payroll_slip", payroll_id=record.id))

@bp.get("/administration/carrousel")
@login_required
def carousel_admin():
    if not user_has_permission(current_user, "settings.manage"):
        flash("Accès aux paramètres non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    slides=HomeSlide.query.order_by(HomeSlide.position, HomeSlide.id).all()
    return render_template("admin/carousel.html", slides=slides)

@bp.post("/administration/carrousel/nouveau")
@login_required
def carousel_new():
    if not user_has_permission(current_user, "settings.manage"):
        flash("Accès aux paramètres non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    f=request.form; title=f.get("title", "").strip()
    if not title: flash("Le titre est obligatoire.", "danger")
    else:
        slide=HomeSlide(title=title, subtitle=f.get("subtitle") or None, image_url=f.get("image_url") or None, button_label=f.get("button_label") or "Accéder à la plateforme", button_url=f.get("button_url") or "/connexion", position=int(f.get("position") or 0), active=bool(f.get("active")))
        db.session.add(slide); db.session.commit(); flash("Diapositive ajoutée.", "success")
    return redirect(url_for("main.carousel_admin"))

@bp.post("/administration/carrousel/<int:slide_id>/modifier")
@login_required
def carousel_edit(slide_id):
    if not user_has_permission(current_user, "settings.manage"):
        flash("Accès aux paramètres non autorisé.", "danger"); return redirect(url_for("main.dashboard"))
    slide=db.get_or_404(HomeSlide, slide_id); f=request.form; slide.title=f.get("title", "").strip(); slide.subtitle=f.get("subtitle") or None; slide.image_url=f.get("image_url") or None; slide.button_label=f.get("button_label") or "En savoir plus"; slide.button_url=f.get("button_url") or "/connexion"; slide.position=int(f.get("position") or 0); slide.active=bool(f.get("active")); db.session.commit(); flash("Diapositive modifiée.", "success"); return redirect(url_for("main.carousel_admin"))


# --- Rapports de gestion fondés sur les données enregistrées ---
@bp.route("/rapports/gestion")
@login_required
def management_reports():
    try:
        debut=date.fromisoformat(request.args.get("debut","")) if request.args.get("debut") else date.today().replace(day=1)
        fin=date.fromisoformat(request.args.get("fin","")) if request.args.get("fin") else date.today()
        if fin<debut: raise ValueError()
    except ValueError:
        flash("Période invalide.","danger"); debut=date.today().replace(day=1); fin=date.today()
    dt0=datetime.combine(debut,datetime.min.time()); dt1=datetime.combine(fin+timedelta(days=1),datetime.min.time())
    paid=db.session.query(Payment.currency,func.coalesce(func.sum(Payment.amount),0)).filter(Payment.paid_at>=dt0,Payment.paid_at<dt1).group_by(Payment.currency).all()
    expenses=db.session.query(Expense.currency,func.coalesce(func.sum(Expense.amount),0)).filter(Expense.incurred_at>=debut,Expense.incurred_at<=fin,Expense.status.in_(["VALIDEE","PAYEE","APPROUVEE"])).group_by(Expense.currency).all()
    invoices=Invoice.query.filter(Invoice.issued_at>=dt0,Invoice.issued_at<dt1).count()
    visits=ReceptionVisit.query.filter(ReceptionVisit.visit_date>=debut,ReceptionVisit.visit_date<=fin).count()
    consults=ClinicalConsultation.query.filter(ClinicalConsultation.consulted_at>=dt0,ClinicalConsultation.consulted_at<dt1).count()
    admissions=Admission.query.filter(Admission.admitted_at>=dt0,Admission.admitted_at<dt1).count()
    patients=Patient.query.filter(Patient.created_at>=dt0,Patient.created_at<dt1).count()
    totals=db.session.query(Invoice.currency,func.coalesce(func.sum(InvoiceLine.quantity*InvoiceLine.unit_price),0)).join(InvoiceLine,InvoiceLine.invoice_id==Invoice.id).filter(Invoice.issued_at<dt1,Invoice.status.notin_(["ANNULEE","BROUILLON"])).group_by(Invoice.currency).all()
    debts=[]
    for cur,total in totals:
        paid_total=db.session.query(func.coalesce(func.sum(Payment.amount),0)).join(Invoice,Payment.invoice_id==Invoice.id).filter(Invoice.currency==cur,Invoice.issued_at<dt1,Invoice.status.notin_(["ANNULEE","BROUILLON"])).scalar() or 0
        debts.append({"currency":cur,"amount":max(0,float(total)-float(paid_total))})
    daily=db.session.query(ReceptionVisit.visit_date,func.count(ReceptionVisit.id)).filter(ReceptionVisit.visit_date>=debut,ReceptionVisit.visit_date<=fin).group_by(ReceptionVisit.visit_date).order_by(ReceptionVisit.visit_date).all()
    return render_template("reports/management.html",start_date=debut,end_date=fin,cash=[{"currency":c,"amount":float(v)} for c,v in paid],expenses=[{"currency":c,"amount":float(v)} for c,v in expenses],debts=debts,invoices=invoices,visits=visits,consults=consults,admissions=admissions,patients=patients,daily=[{"date":d.strftime("%d/%m"),"count":n} for d,n in daily])

@bp.route("/rapports/gestion/export.csv")
@login_required
def management_reports_csv():
    from io import StringIO
    import csv
    try:
        debut=date.fromisoformat(request.args.get("debut","")) if request.args.get("debut") else date.today().replace(day=1)
        fin=date.fromisoformat(request.args.get("fin","")) if request.args.get("fin") else date.today()
        if fin<debut: raise ValueError()
    except ValueError:
        flash("Période invalide.","danger"); return redirect(url_for("main.management_reports"))
    dt0=datetime.combine(debut,datetime.min.time()); dt1=datetime.combine(fin+timedelta(days=1),datetime.min.time())
    out=StringIO(); w=csv.writer(out,delimiter=";"); w.writerow(["Indicateur","Devise","Valeur","Période"])
    for c,v in db.session.query(Payment.currency,func.sum(Payment.amount)).filter(Payment.paid_at>=dt0,Payment.paid_at<dt1).group_by(Payment.currency): w.writerow(["Encaissements",c,v,f"{debut} - {fin}"])
    for c,v in db.session.query(Expense.currency,func.sum(Expense.amount)).filter(Expense.incurred_at>=debut,Expense.incurred_at<=fin,Expense.status.in_(["VALIDEE","PAYEE","APPROUVEE"])).group_by(Expense.currency): w.writerow(["Dépenses validées",c,v,f"{debut} - {fin}"])
    w.writerow(["Factures émises","",Invoice.query.filter(Invoice.issued_at>=dt0,Invoice.issued_at<dt1).count(),f"{debut} - {fin}"])
    w.writerow(["Passages","",ReceptionVisit.query.filter(ReceptionVisit.visit_date>=debut,ReceptionVisit.visit_date<=fin).count(),f"{debut} - {fin}"])
    response=make_response("\\ufeff"+out.getvalue()); response.headers["Content-Type"]="text/csv; charset=utf-8"; response.headers["Content-Disposition"]=f"attachment; filename=rapport_{debut}_{fin}.csv"
    return response


@bp.route("/rapports/activite-medicale")
@login_required
def medical_activity_reports():
    if not user_has_permission(current_user, "reports.view"):
        flash("Accès non autorisé.", "danger")
        return redirect(url_for("main.dashboard"))
    debut=date.fromisoformat(request.args.get("debut")) if request.args.get("debut") else date.today().replace(day=1)
    fin=date.fromisoformat(request.args.get("fin")) if request.args.get("fin") else date.today()
    if fin < debut:
        flash("Période invalide.", "danger")
        return redirect(url_for("main.medical_activity_reports"))
    d0=datetime.combine(debut,datetime.min.time()); d1=datetime.combine(fin+timedelta(days=1),datetime.min.time())
    services=db.session.query(HospitalService.name,func.count(ReceptionVisit.id)).join(ReceptionVisit,ReceptionVisit.service_id==HospitalService.id).filter(ReceptionVisit.visit_date>=debut,ReceptionVisit.visit_date<=fin).group_by(HospitalService.name).all()
    labs=db.session.query(LabTest.name,func.count(LabOrder.id)).join(LabOrder,LabOrder.test_id==LabTest.id).filter(LabOrder.requested_at>=d0,LabOrder.requested_at<d1).group_by(LabTest.name).all()
    disp=db.session.query(StockItem.name,func.sum(PharmacyDispenseLine.quantity)).join(StockBatch,StockBatch.item_id==StockItem.id).join(PharmacyDispenseLine,PharmacyDispenseLine.batch_id==StockBatch.id).join(PharmacyDispense,PharmacyDispense.id==PharmacyDispenseLine.dispense_id).filter(PharmacyDispense.dispensed_at>=d0,PharmacyDispense.dispensed_at<d1,PharmacyDispense.status=="VALIDEE").group_by(StockItem.name).all()
    low=db.session.query(StockItem).outerjoin(StockBatch,StockBatch.item_id==StockItem.id).group_by(StockItem.id).having(func.coalesce(func.sum(StockBatch.quantity_remaining),0)<=func.coalesce(StockItem.alert_threshold,0)).all()
    return render_template("reports/medical_activity.html",debut=debut,fin=fin,services=[{"name":n,"count":c} for n,c in services],labs=[{"name":n,"count":c} for n,c in labs],disp=[{"name":n,"qty":float(q or 0)} for n,q in disp],low=low,consults=ClinicalConsultation.query.filter(ClinicalConsultation.consulted_at>=d0,ClinicalConsultation.consulted_at<d1).count(),admissions=Admission.query.filter(Admission.admitted_at>=d0,Admission.admitted_at<d1).count(),lab_total=LabOrder.query.filter(LabOrder.requested_at>=d0,LabOrder.requested_at<d1).count(),lab_validated=LabResult.query.join(LabOrder).filter(LabOrder.requested_at>=d0,LabOrder.requested_at<d1,LabResult.validated_at.isnot(None)).count())

@bp.route("/rapports/activite-medicale/export.csv")
@login_required
def medical_activity_reports_csv():
    if not user_has_permission(current_user, "reports.view"):
        flash("Accès non autorisé.", "danger")
        return redirect(url_for("main.dashboard"))
    from io import StringIO
    import csv
    debut=date.fromisoformat(request.args.get("debut")) if request.args.get("debut") else date.today().replace(day=1)
    fin=date.fromisoformat(request.args.get("fin")) if request.args.get("fin") else date.today()
    d0=datetime.combine(debut,datetime.min.time()); d1=datetime.combine(fin+timedelta(days=1),datetime.min.time())
    out=StringIO(); w=csv.writer(out,delimiter=";"); w.writerow(["Indicateur","Catégorie","Valeur"])
    for n,c in db.session.query(HospitalService.name,func.count(ReceptionVisit.id)).join(ReceptionVisit,ReceptionVisit.service_id==HospitalService.id).filter(ReceptionVisit.visit_date>=debut,ReceptionVisit.visit_date<=fin).group_by(HospitalService.name): w.writerow(["Passages par service",n,c])
    for n,c in db.session.query(LabTest.name,func.count(LabOrder.id)).join(LabOrder).filter(LabOrder.requested_at>=d0,LabOrder.requested_at<d1).group_by(LabTest.name): w.writerow(["Analyses demandées",n,c])
    response=make_response("\ufeff"+out.getvalue()); response.headers["Content-Type"]="text/csv; charset=utf-8"; response.headers["Content-Disposition"]="attachment; filename=rapport_activite_medicale.csv"
    return response

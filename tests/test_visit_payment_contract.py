from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_invoice_patient_without_admission():
 s=(ROOT/"app/models.py").read_text(); block=s.split("class Invoice(db.Model):",1)[1].split("class InvoiceLine",1)[0]
 assert 'admission_id=db.Column(db.ForeignKey("admissions.id"),nullable=True)' in block
 assert 'patient_id=db.Column(db.ForeignKey("patients.id"),nullable=True' in block
def test_visit_links_invoice():
 s=(ROOT/"app/models.py").read_text(); block=s.split("class ReceptionVisit(db.Model):",1)[1].split("class TriageAssessment",1)[0]
 assert 'invoice_id = db.Column(db.ForeignKey("invoices.id"), nullable=True' in block
def test_visit_creation_requires_full_payment():
 s=(ROOT/"app/routes.py").read_text(); block=s.split("def invoice_open_visit",1)[1].split("# --- Accueil",1)[0]
 assert 'invoice.balance > covered' in block and 'ReceptionVisit.query.filter_by(invoice_id=invoice.id).first()' in block
def test_new_passage_uses_existing_patient():
 s=(ROOT/"app/routes.py").read_text(); assert 'def patient_visit_invoice(patient_id):' in s and 'patient = db.get_or_404(Patient, patient_id)' in s

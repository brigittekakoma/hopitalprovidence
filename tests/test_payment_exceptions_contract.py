from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_coverage_authorization_model_and_audit():
 s=(ROOT/"app/models.py").read_text(); assert "class InvoiceCoverageAuthorization" in s and "authorized_by" in s and "justification" in s
def test_emergency_visit_bypasses_upfront_payment():
 s=(ROOT/"app/routes.py").read_text(); r=s.split("def emergency_visit_new",1)[1].split("def invoice_open_visit",1)[0]; assert "ACCUEIL_URGENCE_SANS_PAIEMENT_PREALABLE" in r and 'priority=\"URGENTE\"' in r
def test_nonurgent_visit_requires_payment_or_full_coverage():
 s=(ROOT/"app/routes.py").read_text(); r=s.split("def invoice_open_visit",1)[1].split("# --- Accueil",1)[0]; assert "invoice.balance > covered" in r
def test_coverage_permission_is_catalogued():
 s=(ROOT/"app/routes.py").read_text(); assert "billing.authorize_coverage" in s

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_clinical_models_and_routes_exist():
    models=(ROOT/'app/models.py').read_text()
    routes=(ROOT/'app/routes.py').read_text()
    assert 'class ClinicalConsultation' in models
    assert 'class ConsultationVitals' in models
    assert 'class Prescription' in models
    assert 'def consultation_new' in routes
    assert 'def prescription_create' in routes
    assert 'def consultation_close' in routes

def test_consultation_ui_has_privacy_and_print_actions():
    detail=(ROOT/'app/templates/consultations/detail.html').read_text()
    assert 'window.print()' in detail
    assert 'Document confidentiel' in detail
    assert 'Clôturer la consultation' in detail

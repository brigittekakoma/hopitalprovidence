from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_payroll_models_and_routes_exist():
    models=(ROOT/'app/models.py').read_text(); routes=(ROOT/'app/routes.py').read_text()
    assert 'class PayrollRecord' in models and 'class PayrollComponent' in models
    assert 'def payroll_new' in routes and 'def payroll_slip' in routes

def test_patient_and_staff_cards_are_linked_to_existing_records():
    routes=(ROOT/'app/routes.py').read_text()
    patients=(ROOT/'app/templates/patients/list.html').read_text()
    staff=(ROOT/'app/templates/hr/staff.html').read_text()
    assert 'def patient_card' in routes and 'def staff_card' in routes
    assert 'main.patient_card' in patients and 'main.staff_card' in staff
    assert 'url_for("main.patient_card", patient_id=patient.id)' in routes
    assert 'url_for("main.staff_card", staff_id=profile.id)' in routes

def test_home_carousel_is_editable():
    models=(ROOT/'app/models.py').read_text(); routes=(ROOT/'app/routes.py').read_text(); home=(ROOT/'app/templates/home.html').read_text()
    assert 'class HomeSlide' in models
    assert 'def carousel_admin' in routes and 'def carousel_new' in routes and 'def carousel_edit' in routes
    assert 'data-slide' in home and 'slide-next' in home

def test_no_default_statutory_payroll_rates():
    payroll=(ROOT/'app/templates/hr/payroll.html').read_text()
    assert 'Aucun taux légal ou montant salarial n’est préprogrammé' in payroll

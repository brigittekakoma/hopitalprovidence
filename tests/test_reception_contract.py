from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reception_models_and_queue_uniqueness_exist():
    models = (ROOT / "app" / "models.py").read_text(encoding="utf-8")
    assert "class Appointment(db.Model)" in models
    assert "class ReceptionVisit(db.Model)" in models
    assert "class TriageAssessment(db.Model)" in models
    assert "uq_queue_number_per_day" in models


def test_reception_routes_cover_schedule_checkin_triage_and_orientation():
    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    for endpoint in ("def reception():", "def appointment_new():", "def reception_checkin():", "def reception_triage(visit_id):", "def reception_orient(visit_id):"):
        assert endpoint in routes
    assert '"CRITIQUE"' in routes and '"URGENTE"' in routes


def test_reception_ui_and_navigation_exist():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    page = ROOT / "app" / "templates" / "reception" / "index.html"
    form = ROOT / "app" / "templates" / "reception" / "appointment_form.html"
    assert page.exists() and form.exists()
    assert "main.reception" in base
    assert "Enregistrer le triage" in page.read_text(encoding="utf-8")

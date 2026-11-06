from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_duplicate_search_endpoint_and_server_guard_exist():
    source = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    assert '"/patients/recherche-doublons"' in source
    assert "_find_existing_patient(name, phone, birth_date)" in source
    assert "patient_duplicate_search" in source

def test_patient_form_warns_and_links_existing_record():
    source = (ROOT / "app" / "templates" / "patients" / "form.html").read_text(encoding="utf-8")
    assert "duplicate-panel" in source
    assert "Ouvrir le dossier" in source
    assert "fetch(" in source

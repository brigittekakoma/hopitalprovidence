from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_production_secret_is_enforced():
    source = (ROOT / "app" / "__init__.py").read_text()
    assert "SECRET_KEY doit être défini" in source
    assert "len(configured_secret) < 32" in source

def test_backup_and_restore_are_cli_only():
    source = (ROOT / "app" / "__init__.py").read_text()
    assert '@app.cli.command("backup-db")' in source
    assert '@app.cli.command("restore-db")' in source
    assert '"RESTAURER"' in source

def test_sensitive_access_audit_avoids_medical_payload():
    source = (ROOT / "app" / "__init__.py").read_text()
    assert "audit_sensitive_access" in source
    assert "CONSULTATION_DOSSIER" in source
    assert "request.form" not in source[source.index("def audit_sensitive_access"):source.index("def security_headers")]

def test_session_and_http_security_controls():
    source = (ROOT / "app" / "__init__.py").read_text()
    auth = (ROOT / "app" / "auth.py").read_text()
    assert "SESSION_COOKIE_HTTPONLY=True" in source
    assert 'SESSION_COOKIE_SAMESITE="Lax"' in source
    assert "session.permanent = True" in auth
    assert "Strict-Transport-Security" in source

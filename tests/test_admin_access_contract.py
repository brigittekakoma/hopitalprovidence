from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_staff_roles_and_audit_routes_exist():
    routes = (ROOT / 'app' / 'routes.py').read_text()
    assert 'def staff_admin' in routes
    assert 'def staff_new' in routes
    assert 'def staff_edit' in routes
    assert 'def roles_admin' in routes
    assert 'def audit_admin' in routes

def test_permission_catalog_covers_sensitive_domains():
    routes = (ROOT / 'app' / 'routes.py').read_text()
    for code in ('patients.view', 'clinical.view', 'billing.collect', 'pharmacy.manage', 'laboratory.manage', 'staff.manage', 'audit.view'):
        assert code in routes

def test_bootstrap_commands_are_available():
    app = (ROOT / 'app' / '__init__.py').read_text()
    assert 'def init_access' in app
    assert 'def create_admin' in app
    assert 'confirmation_prompt=True' in app

def test_admin_templates_exist():
    templates = ROOT / 'app' / 'templates' / 'admin'
    for name in ('staff.html', 'staff_form.html', 'roles.html', 'audit.html'):
        assert (templates / name).is_file()

from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_hr_models_exist():
    source = (ROOT / 'app' / 'models.py').read_text()
    for model in ('StaffProfile', 'StaffAttendance', 'StaffLeaveRequest'):
        assert f'class {model}' in source

def test_hr_routes_and_templates_exist():
    source = (ROOT / 'app' / 'routes.py').read_text()
    for route in ('/rh/personnel', '/rh/presences', '/rh/conges'):
        assert route in source
    for template in ('staff.html', 'attendance.html', 'leaves.html'):
        assert (ROOT / 'app' / 'templates' / 'hr' / template).exists()

def test_hr_permission_is_catalogued_and_guarded():
    routes = (ROOT / 'app' / 'routes.py').read_text()
    init = (ROOT / 'app' / '__init__.py').read_text()
    assert '"hr.manage"' in routes
    assert 'endpoint.startswith("main.hr_")' in init

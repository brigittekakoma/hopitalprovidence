from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_medical_reports_use_real_models():
 s=(ROOT/'app/routes.py').read_text()
 for m in ['ReceptionVisit','ClinicalConsultation','Admission','LabOrder','PharmacyDispenseLine','StockBatch']: assert m in s
def test_lab_validation_timestamp_is_used():
 assert 'LabResult.validated_at.isnot(None)' in (ROOT/'app/routes.py').read_text()
def test_csv_export_exists():
 assert 'def medical_activity_reports_csv()' in (ROOT/'app/routes.py').read_text()
def test_report_permission_is_checked():
 assert 'user_has_permission(current_user, "reports.view")' in (ROOT/'app/routes.py').read_text()

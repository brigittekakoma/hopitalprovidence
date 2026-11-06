from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_real_transactions_and_currency_separation():
 s=(ROOT/'app/routes.py').read_text()
 assert 'Payment.paid_at>=dt0' in s and 'Expense.incurred_at>=debut' in s
 assert 'group_by(Payment.currency)' in s and 'group_by(Expense.currency)' in s
def test_real_activity_models():
 s=(ROOT/'app/routes.py').read_text()
 for m in ['ReceptionVisit','ClinicalConsultation','Admission','Patient']: assert m in s
def test_csv_export_route():
 assert 'def management_reports_csv()' in (ROOT/'app/routes.py').read_text()

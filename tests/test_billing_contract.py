from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_billing_routes_and_templates_exist():
    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    assert '"/facturation"' in routes
    assert '"/facturation/factures"' in routes
    assert '"/facturation/<int:invoice_id>/paiements"' in routes
    assert '"/facturation/recu/<int:payment_id>"' in routes
    for name in ("index.html", "detail.html", "receipt.html"):
        assert (ROOT / "app" / "templates" / "billing" / name).is_file()


def test_currency_and_overpayment_guards_exist():
    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    assert 'currency not in {"CDF","USD"}' in routes
    assert 'amount > invoice.balance' in routes


def test_pharmacy_routes_and_templates_exist():
    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    models = (ROOT / "app" / "models.py").read_text(encoding="utf-8")
    assert "def pharmacy_item_create" in routes
    assert "def pharmacy_receive_batch" in routes
    assert "def pharmacy_dispense" in routes
    assert "class StockBatch" in models
    assert "class PharmacyDispense" in models
    assert (ROOT / "app" / "templates" / "pharmacy" / "index.html").is_file()
    assert (ROOT / "app" / "templates" / "pharmacy" / "movements.html").is_file()


def test_pharmacy_fefo_and_expiry_protection_exist():
    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    assert "StockBatch.expiry_date >= today" in routes
    assert "with_for_update()" in routes
    assert "order_by(StockBatch.expiry_date.is_(None), StockBatch.expiry_date.asc()" in routes

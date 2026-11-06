-- Sauvegarder la base avant exécution. Migration PostgreSQL.
CREATE TABLE IF NOT EXISTS invoice_coverage_authorizations (
 id SERIAL PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id),
 coverage_type VARCHAR(24) NOT NULL CHECK (coverage_type IN ('ASSURANCE','EXEMPTION','CREDIT','URGENCE')),
 amount_covered NUMERIC(14,2) NOT NULL CHECK (amount_covered > 0), reference VARCHAR(100),
 justification TEXT NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'VALIDEE',
 authorized_by INTEGER NOT NULL REFERENCES users(id), authorized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_invoice_coverage_authorizations_invoice_id ON invoice_coverage_authorizations(invoice_id);

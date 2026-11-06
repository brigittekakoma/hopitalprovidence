-- Migration PostgreSQL à exécuter après sauvegarde de la base.
-- Vérifier d'abord les noms de contraintes dans la base cible.
ALTER TABLE invoices ALTER COLUMN admission_id DROP NOT NULL;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS patient_id INTEGER NULL REFERENCES patients(id);
CREATE INDEX IF NOT EXISTS ix_invoices_patient_id ON invoices(patient_id);
ALTER TABLE reception_visits ADD COLUMN IF NOT EXISTS invoice_id INTEGER NULL REFERENCES invoices(id);
CREATE INDEX IF NOT EXISTS ix_reception_visits_invoice_id ON reception_visits(invoice_id);

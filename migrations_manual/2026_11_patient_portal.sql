-- Portail patient : exécuter après sauvegarde de la base et sur l'environnement cible.
CREATE TABLE patient_portal_accounts (
 id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL UNIQUE REFERENCES patients(id),
 email VARCHAR(160) NOT NULL UNIQUE, password_hash VARCHAR(255),
 activation_token_hash VARCHAR(64) UNIQUE, activation_expires_at TIMESTAMP,
 active BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, last_login_at TIMESTAMP
);
CREATE INDEX ix_patient_portal_accounts_patient_id ON patient_portal_accounts(patient_id);
CREATE INDEX ix_patient_portal_accounts_email ON patient_portal_accounts(email);
CREATE TABLE patient_appointment_change_requests (
 id SERIAL PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
 appointment_id INTEGER NOT NULL REFERENCES appointments(id), request_type VARCHAR(20) NOT NULL,
 requested_at TIMESTAMP, reason VARCHAR(500), status VARCHAR(20) NOT NULL DEFAULT 'EN_ATTENTE',
 decision_note VARCHAR(500), decided_by INTEGER REFERENCES users(id), decided_at TIMESTAMP,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_patient_appointment_change_patient ON patient_appointment_change_requests(patient_id);
CREATE INDEX ix_patient_appointment_change_appointment ON patient_appointment_change_requests(appointment_id);
CREATE INDEX ix_patient_appointment_change_status ON patient_appointment_change_requests(status);

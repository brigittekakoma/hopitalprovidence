CREATE TABLE IF NOT EXISTS online_appointment_requests (
id SERIAL PRIMARY KEY, request_number VARCHAR(70) UNIQUE NOT NULL, full_name VARCHAR(180) NOT NULL,
email VARCHAR(160) NOT NULL, phone VARCHAR(40) NOT NULL, service_id INTEGER REFERENCES hospital_services(id),
preferred_date DATE NOT NULL, preferred_period VARCHAR(24) NOT NULL DEFAULT 'INDIFFERENT', reason VARCHAR(500),
status VARCHAR(24) NOT NULL DEFAULT 'EN_ATTENTE', patient_id INTEGER REFERENCES patients(id),
appointment_id INTEGER REFERENCES appointments(id), proposed_at TIMESTAMP, decision_note VARCHAR(500),
decided_by INTEGER REFERENCES users(id), decided_at TIMESTAMP, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_online_appointment_requests_status ON online_appointment_requests(status);
CREATE INDEX IF NOT EXISTS ix_online_appointment_requests_preferred_date ON online_appointment_requests(preferred_date);
CREATE INDEX IF NOT EXISTS ix_online_appointment_requests_email ON online_appointment_requests(email);

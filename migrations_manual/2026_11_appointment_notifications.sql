-- Journal des rappels automatiques de rendez-vous. Sauvegarder la base avant application.
CREATE TABLE appointment_notifications (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id),
    reminder_type VARCHAR(20) NOT NULL,
    recipient VARCHAR(160) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'EN_ATTENTE',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error VARCHAR(500),
    sent_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_appointment_reminder_type UNIQUE (appointment_id, reminder_type)
);
CREATE INDEX ix_appointment_notifications_appointment_id ON appointment_notifications(appointment_id);
CREATE INDEX ix_appointment_notifications_status ON appointment_notifications(status);

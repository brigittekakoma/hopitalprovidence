ALTER TABLE appointments ADD COLUMN IF NOT EXISTS professional_id INTEGER REFERENCES staff_profiles(id);
CREATE INDEX IF NOT EXISTS ix_appointments_professional_id ON appointments(professional_id);
CREATE TABLE IF NOT EXISTS professional_schedules (
 id SERIAL PRIMARY KEY, staff_id INTEGER NOT NULL REFERENCES staff_profiles(id),
 weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6), start_time TIME NOT NULL,
 end_time TIME NOT NULL, slot_minutes INTEGER NOT NULL DEFAULT 30 CHECK (slot_minutes IN (15,20,30,45,60,90)),
 active BOOLEAN NOT NULL DEFAULT TRUE, CONSTRAINT uq_professional_schedule_day UNIQUE(staff_id,weekday),
 CONSTRAINT ck_professional_schedule_hours CHECK(start_time < end_time));

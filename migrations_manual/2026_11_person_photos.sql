-- Add optional portrait references without altering existing records.
ALTER TABLE patients ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);
ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);

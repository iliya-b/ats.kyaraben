
ALTER TABLE projects ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE avms ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE avm_commands ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE project_apks ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE project_camera ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE campaigns ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE testruns ALTER COLUMN status_reason TYPE TEXT;
ALTER TABLE testsources ALTER COLUMN status_reason TYPE TEXT;


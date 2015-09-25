
ALTER TABLE images ADD COLUMN system_image TEXT;
ALTER TABLE images ADD COLUMN data_image TEXT;

UPDATE images SET system_image = 'system-' || image;
UPDATE images SET data_image = 'data-' || image;

ALTER TABLE images ALTER COLUMN system_image SET NOT NULL;
ALTER TABLE images ALTER COLUMN data_image SET NOT NULL;


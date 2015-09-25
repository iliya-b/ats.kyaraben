
CREATE TABLE testsources (
    testsource_id buuid PRIMARY KEY,
    filename VARCHAR(128) NOT NULL CHECK (filename <> ''),
    apk_id buuid REFERENCES project_apks,
    project_id buuid NOT NULL REFERENCES projects,
    content VARCHAR NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'UPLOADING' CHECK (status IN ('UPLOADING', 'READY')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT '',
    FOREIGN KEY (project_id, apk_id) REFERENCES project_apks (project_id, apk_id) MATCH SIMPLE
);

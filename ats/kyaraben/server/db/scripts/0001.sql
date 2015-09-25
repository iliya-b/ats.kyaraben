
-- could use a real UUID type but takes a bit more effort on the python side (not serializable, etc)

CREATE DOMAIN buuid AS VARCHAR(32)
    CHECK ((VALUE SIMILAR TO '[a-f0-9]*') AND (LENGTH(VALUE) = 32));


CREATE TABLE projects (
    project_id buuid PRIMARY KEY,
    project_name VARCHAR(50) NOT NULL CHECK (project_name <> ''),
    uid_owner VARCHAR NOT NULL CHECK (uid_owner <> ''),
    ts_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'CREATING', 'READY', 'DELETING', 'DELETED', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);


CREATE TABLE projects_shared (
    project_id buuid NOT NULL REFERENCES projects,
    userid VARCHAR NOT NULL,
    PRIMARY KEY (project_id, userid)
);


CREATE TABLE avms (
    avm_id buuid PRIMARY KEY,
    avm_name VARCHAR(50) NOT NULL CHECK (avm_name <> ''),
    project_id buuid NOT NULL REFERENCES projects,
    uid_owner VARCHAR NOT NULL CHECK (uid_owner <> ''),
    stack_name VARCHAR(128),
    hwconfig JSONB,
    ts_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    image VARCHAR(64),
    novnc_host VARCHAR(64) NOT NULL DEFAULT '',
    novnc_port INTEGER NOT NULL DEFAULT -1,
    sound_port INTEGER NOT NULL DEFAULT -1,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'CREATING', 'READY', 'DELETING', 'DELETED', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);


CREATE TABLE avmotp (
    avm_id buuid PRIMARY KEY,
    vnc_secret VARCHAR(128) NOT NULL
);


CREATE OR REPLACE VIEW permission_projects AS
     SELECT project_id, project_name, uid_owner AS userid
       FROM projects
      WHERE status <> 'DELETED'
  UNION ALL
     SELECT projects.project_id, projects.project_name, projects_shared.userid
       FROM projects_shared
  LEFT JOIN projects ON projects.project_id = projects_shared.project_id
      WHERE projects.status <> 'DELETED';


CREATE OR REPLACE VIEW permission_avms AS
    SELECT avms.avm_id, permission_projects.userid
      FROM permission_projects
      JOIN avms
        ON avms.project_id = permission_projects.project_id
     WHERE avms.status <> 'DELETED';


CREATE TABLE jwt (
    token VARCHAR NOT NULL PRIMARY KEY,
    uid VARCHAR NOT NULL,
    issued_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked INTEGER NOT NULL CHECK (is_revoked IN (0, 1)) DEFAULT 0
);
CREATE INDEX ON jwt (uid);
CREATE INDEX ON jwt (expires_at);


CREATE TABLE avm_commands (
    command_id buuid PRIMARY KEY,
    avm_id buuid NOT NULL REFERENCES avms,
    command TEXT CHECK (command <> ''),
    ts_request TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ts_begin TIMESTAMP,
    ts_end TIMESTAMP,
    proc_returncode INTEGER,
    proc_stdout TEXT,
    proc_stderr TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'READY', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);


CREATE TABLE project_apks (
    apk_id buuid PRIMARY KEY,
    filename VARCHAR(128) NOT NULL CHECK (filename <> ''),
    project_id buuid NOT NULL REFERENCES projects,
    package VARCHAR,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'UPLOADING', 'COMPILING DSL', 'COMPILING JAVA', 'READY', 'DELETING', 'DELETED', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX ON project_apks (project_id, apk_id);


CREATE TABLE project_camera (
    camera_id buuid PRIMARY KEY,
    filename VARCHAR(128) NOT NULL CHECK (filename <> ''),
    project_id buuid NOT NULL REFERENCES projects,
    status VARCHAR(20) NOT NULL DEFAULT 'UPLOADING' CHECK (status IN ('UPLOADING', 'READY', 'DELETING', 'DELETED', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);


CREATE OR REPLACE FUNCTION iso_timestamp(TIMESTAMP WITH TIME ZONE)
  RETURNS VARCHAR AS $$
    SELECT TO_CHAR($1 AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
$$ LANGUAGE SQL IMMUTABLE;


GRANT SELECT ON avms TO nginx;
GRANT SELECT ON permission_projects TO nginx;
GRANT SELECT ON permission_avms TO nginx;
GRANT SELECT ON jwt TO nginx;

GRANT ALL ON jwt TO atsauth;


CREATE TABLE images (
    image VARCHAR(64) PRIMARY KEY,
    android_version INTEGER
);


INSERT INTO images (image, android_version) VALUES ('kitkat-tablet', 4);
INSERT INTO images (image, android_version) VALUES ('kitkat-phone', 4);
INSERT INTO images (image, android_version) VALUES ('lollipop-tablet', 5);
INSERT INTO images (image, android_version) VALUES ('lollipop-phone', 5);



CREATE TABLE campaigns (
    campaign_id buuid PRIMARY KEY,
    campaign_name VARCHAR(20),
    project_id buuid NOT NULL REFERENCES projects,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'READY', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);

CREATE TABLE testruns (
    testrun_id buuid PRIMARY KEY,
    campaign_id buuid NOT NULL REFERENCES campaigns,
    image VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'READY', 'ERROR')),
    status_ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status_reason VARCHAR(50) NOT NULL DEFAULT ''
);

CREATE TABLE testrun_apks (
    testrun_id buuid REFERENCES testruns,
    apk_id buuid NOT NULL REFERENCES project_apks,
    install_order INTEGER NOT NULL CHECK (install_order > 0),
    command_id buuid REFERENCES avm_commands
);

CREATE TABLE testrun_packages (
    command_id buuid REFERENCES avm_commands,
    testrun_id buuid REFERENCES testruns,
    package VARCHAR NOT NULL
);


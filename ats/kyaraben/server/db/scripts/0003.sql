
COMMENT ON DOMAIN buuid IS 'like an UUID but easier for python to handle';

COMMENT ON COLUMN projects.ts_created IS 'time of creation request';

COMMENT ON COLUMN avms.ts_created IS 'time of creation request';


CREATE TABLE billing (
    avm_id buuid PRIMARY KEY REFERENCES avms,
    ts_started TIMESTAMP,
    ts_stopped TIMESTAMP
);

COMMENT ON COLUMN billing.ts_started IS 'creation time';
COMMENT ON COLUMN billing.ts_stopped IS 'deletion time';

CREATE VIEW avms_uptime AS
    SELECT billing.avm_id,
           EXTRACT(
            SECONDS FROM (
                COALESCE(billing.ts_stopped, CURRENT_TIMESTAMP) - billing.ts_started
            )) AS uptime
      FROM billing;


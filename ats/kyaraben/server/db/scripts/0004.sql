
ALTER TABLE avms ADD COLUMN testrun_id buuid REFERENCES testruns;

CREATE OR REPLACE VIEW avms_uptime AS
    SELECT billing.avm_id,
           EXTRACT(
            EPOCH FROM (
                COALESCE(billing.ts_stopped, CURRENT_TIMESTAMP) - billing.ts_started
            )) AS uptime
      FROM billing;


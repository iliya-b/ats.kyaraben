
ALTER TABLE campaigns DROP CONSTRAINT campaigns_status_check;
ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check CHECK (status IN ('QUEUED', 'RUNNING', 'READY', 'DELETING', 'DELETED', 'ERROR'));

CREATE OR REPLACE VIEW campaign_resources AS
    SELECT testruns.campaign_id,
           testruns.testrun_id,
           avm_id,
           avms.stack_name
      FROM testruns
 LEFT JOIN avms ON avms.testrun_id = testruns.testrun_id;


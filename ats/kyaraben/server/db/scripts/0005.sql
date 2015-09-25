CREATE VIEW quota_usage AS
     SELECT uid_owner,
            SUM((testrun_id IS NULL)::INTEGER) AS live_current,
            SUM((testrun_id IS NOT NULL)::INTEGER) AS async_current
       FROM avms
      WHERE status <> 'DELETED'
   GROUP BY uid_owner;


import uuid

from psycopg2.extras import Json

from ats.util.db import sql, asdicts

from ats.kyaraben.model.android import AndroidVM


class Campaign:
    def __init__(self, *, campaign_id):
        self.campaign_id = campaign_id

    @classmethod
    async def get(cls, dbh, *, campaign_id, project_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM campaigns
             WHERE campaign_id = %s
                   AND project_id = %s
                   AND status <> 'DELETED'
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [campaign_id, project_id, userid])

        if len(rows):
            return cls(campaign_id=campaign_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, campaign_id, campaign_name, project_id, tests):
        await sql(dbh, """
                  INSERT INTO campaigns (
                      campaign_id, campaign_name, project_id
                  ) VALUES (%s, %s, %s)
                  """, [campaign_id, campaign_name, project_id])

        for test in tests:
            image = test['image']
            hwconfig = test.get('hwconfig', AndroidVM.hwconfig_defaults)
            testrun_id = uuid.uuid1().hex
            await sql(dbh, """
                      INSERT INTO testruns (
                          testrun_id, campaign_id, image, hwconfig
                      ) VALUES (%s, %s, %s, %s)
                      """, [testrun_id, campaign_id, image, Json(hwconfig)])

            for idx, apk_id in enumerate(test['apks']):
                await sql(dbh, """
                          INSERT INTO testrun_apks (
                              testrun_id, apk_id, install_order
                          ) VALUES (%s, %s, %s)
                          """, [testrun_id, apk_id, idx + 1])

            for package in test['packages']:
                await sql(dbh, """
                          INSERT INTO testrun_packages (
                              testrun_id, package
                          ) VALUES (%s, %s)
                          """, [testrun_id, package])

    @classmethod
    async def list(cls, dbh, *, userid, project_id):
        rows = await sql(dbh, """
            SELECT campaign_id,
                   campaign_name,
                   project_id,
                   status
              FROM campaigns
             WHERE project_id = %s
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
                   AND status <> 'DELETED'
            """, [project_id, userid])

        return asdicts(rows)

    async def results(self, dbh):
        commands_tot = 0
        commands_ready = 0
        for status, count in (await self.command_statuses(dbh)).items():
            commands_tot += count
            if status == 'READY':
                commands_ready += count

        if commands_tot:
            progress = commands_ready / commands_tot
        else:
            progress = 0

        rows = await sql(dbh, """
            SELECT project_id,
                   campaigns.campaign_id,
                   campaign_name,
                   campaigns.status AS campaign_status,
                   testruns.image,
                   testruns.hwconfig,
                   testrun_packages.package,
                   COALESCE(avm_commands.status, 'QUEUED') AS command_status,
                   COALESCE(avm_commands.proc_stdout, '') AS proc_stdout
              FROM campaigns
         LEFT JOIN testruns
                ON campaigns.campaign_id = testruns.campaign_id
         LEFT JOIN testrun_packages
                ON testruns.testrun_id = testrun_packages.testrun_id
         LEFT JOIN avm_commands
                ON testrun_packages.command_id = avm_commands.command_id
             WHERE campaigns.campaign_id = %s
             """, [self.campaign_id])

        if not rows:
            return None

        ret = {}

        for row in rows:
            ret['project_id'] = row.project_id
            ret['campaign_id'] = row.campaign_id
            ret['campaign_name'] = row.campaign_name
            ret['campaign_status'] = row.campaign_status
            ret['progress'] = progress
            ret.setdefault('tests', [])
            ret['tests'].append({
                'image': row.image,
                'hwconfig': row.hwconfig,
                'package': row.package,
                'status': row.command_status,
                'stdout': row.proc_stdout
            })

        return ret

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE campaigns
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE campaign_id = %s
            """, [status, reason, self.campaign_id])

    async def command_statuses(self, dbh):
        """
        Query the status of all the test commands. Used to know
        when a campaign has finished, or if there are errors.
        """

        rows = await sql(dbh, """
             SELECT COALESCE(avm_commands.status, 'QUEUED') AS status,
                    COUNT(1) AS count
                   FROM campaigns
              LEFT JOIN testruns
                     ON testruns.campaign_id = campaigns.campaign_id
              LEFT JOIN testrun_packages
                     ON testrun_packages.testrun_id = testruns.testrun_id
              LEFT JOIN testrun_apks
                     ON testrun_apks.testrun_id = testruns.testrun_id
              LEFT JOIN avm_commands
                     ON (avm_commands.command_id = testrun_packages.command_id)
                        OR (avm_commands.command_id = testrun_apks.command_id)
                 WHERE campaigns.campaign_id = %s
               GROUP BY avm_commands.status;
            """, [self.campaign_id])

        return {
            row[0]: row[1]
            for row in rows
        }

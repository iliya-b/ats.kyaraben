
import datetime

from psycopg2.extras import Json

from ats.util.db import sql, asdicts

import petname


class AndroidVM:
    def __init__(self, *, avm_id):
        self.avm_id = avm_id

    @classmethod
    async def is_deleted(self, dbh, *, avm_id):
        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM avms
             WHERE avm_id = %s
                   AND status = 'DELETED'
            """, [avm_id])

        return len(rows)

    @classmethod
    async def get(cls, dbh, *, avm_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM permission_avms
             WHERE avm_id = %s
                   AND userid = %s
            """, [avm_id, userid])

        if len(rows):
            return cls(avm_id=avm_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, avm_id, avm_name, userid,
                     project_id, image, hwconfig, testrun_id, vnc_secret):
        ts_created = datetime.datetime.now()

        if not avm_name:
            avm_name = petname.Generate(3, '-')

        await sql(dbh, """
            INSERT INTO avms (
                    avm_id, avm_name, ts_created, uid_owner,
                    project_id, image, hwconfig, testrun_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [avm_id, avm_name, ts_created, userid, project_id, image, Json(hwconfig), testrun_id])

        await sql(dbh, """
            INSERT INTO avmotp (
                    avm_id, vnc_secret
                )
                VALUES (%s, %s)
            """, [avm_id, vnc_secret])

    @classmethod
    async def list(cls, dbh, *, userid, project_id):
        # permission check, including shared projects

        filters = ['AND avms.avm_id IN (SELECT avm_id FROM permission_avms WHERE userid = %s)']
        params = [userid]

        # explicit filter by project_id in addition to permission check

        if project_id:
            filters.append('AND project_id = %s')
            params.append(project_id)

        qry = """
            SELECT avms.avm_id,
                   avm_name,
                   uid_owner AS avm_owner,
                   avms.image,
                   project_id,
                   avms.status,
                   iso_timestamp(ts_created) AS ts_created,
                   COALESCE(avms_uptime.uptime, 0) AS uptime,
                   COALESCE(testruns.campaign_id, '') AS campaign_id
              FROM avms
         LEFT JOIN avms_uptime ON avms.avm_id = avms_uptime.avm_id
         LEFT JOIN testruns ON testruns.testrun_id = avms.testrun_id
             WHERE avms.status <> 'DELETED'
                   %s
            """ % ' '.join(filters)

        rows = await sql(dbh, qry, params)

        return asdicts(rows)

    async def select(self, dbh):
        rows = await sql(dbh, """
            SELECT avms.avm_id,
                   avm_name,
                   uid_owner AS avm_owner,
                   avms.image,
                   project_id,
                   avms.status,
                   iso_timestamp(avms.status_ts) AS status_ts,
                   avms.status_reason,
                   iso_timestamp(ts_created) AS ts_created,
                   avms.hwconfig,
                   COALESCE(avms_uptime.uptime, 0) AS uptime,
                   COALESCE(testruns.campaign_id, '') AS campaign_id
              FROM avms
         LEFT JOIN avms_uptime ON avms_uptime.avm_id = avms.avm_id
         LEFT JOIN testruns ON testruns.testrun_id = avms.testrun_id
             WHERE avms.avm_id = %s
                   AND avms.status <> 'DELETED'
            """, [self.avm_id])

        if not rows:
            return None

        return rows[0]._asdict()

    async def get_stack_name(self, dbh):
        rows = await sql(dbh, """
            SELECT stack_name
              FROM avms
             WHERE avm_id = %s
            """, [self.avm_id])

        if not rows:
            return None

        return rows[0].stack_name

    async def get_project_id(self, dbh):
        rows = await sql(dbh, """
            SELECT project_id
              FROM avms
             WHERE avm_id = %s
            """, [self.avm_id])

        if not rows:
            return None

        return rows[0].project_id

    async def update_stack_name(self, dbh, *, stack_name):
        await sql(dbh, """
            UPDATE avms
               SET stack_name = %s
             WHERE avm_id = %s
            """, [stack_name, self.avm_id])

    async def update(self, dbh, *, avm_name):
        await sql(dbh, """
            UPDATE avms
               SET avm_name = %s
             WHERE avm_id = %s
            """, [avm_name, self.avm_id])

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE avms
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE avm_id = %s
            """, [status, reason, self.avm_id])

    @classmethod
    async def count(cls, dbh, *, uid_owner):
        rows = await sql(dbh, """
            SELECT live_current, async_current
              FROM quota_usage
             WHERE uid_owner = %s
            """, [uid_owner])
        if rows:
            return rows[0]._asdict()
        else:
            return {'live_current': 0, 'async_current': 0}

    async def start_billing(self, dbh):
        ts_started = datetime.datetime.now()
        await sql(dbh, """
            INSERT INTO billing (avm_id, ts_started)
                 SELECT %s, %s
                  WHERE NOT EXISTS (SELECT 1 FROM billing WHERE avm_id = %s)
            """, [self.avm_id, ts_started, self.avm_id])

    async def stop_billing(self, dbh):
        ts_stopped = datetime.datetime.now()
        await sql(dbh, """
            UPDATE billing
               SET ts_stopped = %s
             WHERE avm_id = %s
            """, [ts_stopped, self.avm_id])

    hwconfig_defaults = {
        'width': 800,
        'height': 600,
        'dpi': 160,
        'enable_sensors': 1,
        'enable_battery': 1,
        'enable_gps': 1,
        'enable_camera': 1,
        'enable_record': 0,
        'enable_gsm': 1,
        'enable_nfc': 0,
    }

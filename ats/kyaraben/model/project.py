
from ats.util.db import sql, asdicts


class Project:
    def __init__(self, *, project_id):
        self.project_id = project_id

    @classmethod
    async def is_deleted(self, dbh, *, project_id):
        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM projects
             WHERE project_id = %s
                   AND status = 'DELETED'
            """, [project_id])

        return len(rows)

    @classmethod
    async def get(cls, dbh, *, project_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM permission_projects
             WHERE project_id = %s
                   AND userid = %s
            """, [project_id, userid])

        if len(rows):
            return cls(project_id=project_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, project_id, project_name, userid):
        await sql(dbh, """
            INSERT INTO projects (
                project_id, project_name, uid_owner
            ) VALUES (
                %s, %s, %s
            )""", [project_id, project_name, userid])
        return cls(project_id=project_id)

    @classmethod
    async def list(cls, dbh, *, userid):
        rows = await sql(dbh, """
            SELECT project_id, project_name, status
              FROM projects
             WHERE project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
             """, [userid])

        return asdicts(rows)

    async def select(self, dbh):
        rows = await sql(dbh, """
            SELECT projects.project_id,
                   project_name,
                   projects.status,
                   iso_timestamp(projects.status_ts) AS status_ts,
                   projects.status_reason,
                   COALESCE(SUM(avms_uptime.uptime), 0) AS sum_avms_uptime,
                   COUNT(avms_uptime.avm_id) AS count_avms
              FROM projects
              LEFT JOIN avms ON avms.project_id = projects.project_id
              LEFT JOIN avms_uptime ON avms_uptime.avm_id = avms.avm_id
             WHERE projects.project_id = %s
                   AND projects.status <> 'DELETED'
          GROUP BY projects.project_id;
            """, [self.project_id])

        return rows[0]._asdict()

    async def update(self, dbh, *, project_name):
        await sql(dbh, """
            UPDATE projects
               SET project_name = %s
             WHERE project_id = %s
            """, [project_name, self.project_id])

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE projects
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE project_id = %s
            """, [status, reason, self.project_id])

    async def is_active(self, dbh):
        """
        A project is active (i.e. cannot be deleted) if it has VMs that have
        not been deleted, or asynchronous campaigns that will create VMs.
        """

        rows = await sql(dbh, """
                SELECT 1 AS dummy
                  FROM avms
                 WHERE project_id = %s
                       AND status <> 'DELETED'
                UNION ALL
                SELECT 1
                  FROM campaigns
                 WHERE project_id = %s
                       AND status in ('QUEUED', 'RUNNING')
        """, [self.project_id, self.project_id])
        return bool(rows)

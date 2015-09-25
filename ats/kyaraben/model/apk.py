
from ats.util.db import sql, asdicts


class APK:
    def __init__(self, *, apk_id):
        self.apk_id = apk_id

    @classmethod
    async def is_deleted(self, dbh, *, apk_id):
        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM project_apks
             WHERE apk_id = %s
                   AND status = 'DELETED'
            """, [apk_id])

        return len(rows)

    @classmethod
    async def get(cls, dbh, *, apk_id, project_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM project_apks
             WHERE apk_id = %s
                   AND project_id = %s
                   AND status <> 'DELETED'
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [apk_id, project_id, userid])

        if len(rows):
            return cls(apk_id=apk_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, apk_id, filename, project_id, package=''):
        await sql(dbh, """
            DELETE FROM project_apks
                  WHERE apk_id = %s
            """, [apk_id])
        await sql(dbh, """
            INSERT INTO project_apks (
                    apk_id, filename, project_id, package
                ) VALUES (%s, %s, %s, %s)
            """, [apk_id, filename, project_id, package])

    @classmethod
    async def list(cls, dbh, *, userid, project_id):
        rows = await sql(dbh, """
            SELECT project_apks.apk_id,
                   project_apks.filename,
                   project_apks.project_id,
                   COALESCE(testsources.testsource_id, '') AS testsource_id,
                   COALESCE(project_apks.package, '') AS package,
                   project_apks.status
              FROM project_apks
         LEFT JOIN testsources ON testsources.apk_id = project_apks.apk_id
             WHERE project_apks.project_id = %s
                   AND project_apks.status <> 'DELETED'
                   AND project_apks.project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [project_id, userid])

        return asdicts(rows)

    async def select(self, dbh):
        rows = await sql(dbh, """
            SELECT apk_id,
                   filename,
                   project_id,
                   COALESCE(package, '') AS package,
                   status,
                   status_reason
              FROM project_apks
             WHERE apk_id = %s
            """, [self.apk_id])

        return rows[0]._asdict()

    async def get_package_name(self, dbh):
        rows = await sql(dbh, """
            SELECT package
              FROM project_apks
             WHERE apk_id = %s
            """, [self.apk_id])

        return rows[0].package

    async def set_package_name(self, dbh, package):
        await sql(dbh, """
            UPDATE project_apks
               SET package = %s
             WHERE apk_id = %s
            """, [package, self.apk_id])

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE project_apks
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE apk_id = %s
            """, [status, reason, self.apk_id])

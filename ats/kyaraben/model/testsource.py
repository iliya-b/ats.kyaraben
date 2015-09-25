
from ats.util.db import sql, asdicts


class Testsource:
    def __init__(self, *, testsource_id):
        self.testsource_id = testsource_id

    @classmethod
    async def get(cls, dbh, *, testsource_id, project_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM testsources
             WHERE testsource_id = %s
                   AND project_id = %s
                   AND status <> 'DELETED'
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [testsource_id, project_id, userid])

        if len(rows):
            return cls(testsource_id=testsource_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, testsource_id, filename, project_id, content):
        await sql(dbh, """
            INSERT INTO testsources (
                    testsource_id,
                    filename,
                    project_id,
                    content
                ) VALUES (%s, %s, %s, %s)
            """, [testsource_id, filename, project_id, content])

    async def update_apk(self, dbh, *, apk_id):
        await sql(dbh, """
            UPDATE testsources
               SET apk_id = %s
             WHERE testsource_id = %s
            """, [apk_id, self.testsource_id])

    async def update(self, dbh, *, filename, content):
        await sql(dbh, """
            UPDATE testsources
               SET filename = %s,
                   content = %s
             WHERE testsource_id = %s
            """, [filename, content, self.testsource_id])

    @classmethod
    async def list(cls, dbh, *, userid, project_id):
        rows = await sql(dbh, """
            SELECT testsources.testsource_id,
                   testsources.filename,
                   testsources.project_id,
                   COALESCE(testsources.apk_id, '') AS apk_id,
                   testsources.status,
                   COALESCE(project_apks.status, '') AS apk_status,
                   COALESCE(project_apks.status_reason, '') AS apk_status_reason
              FROM testsources
         LEFT JOIN project_apks
                ON project_apks.apk_id = testsources.apk_id
             WHERE testsources.project_id = %s
                   AND testsources.status <> 'DELETED'
                   AND testsources.project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [project_id, userid])

        return asdicts(rows)

    async def content(self, dbh):
        ret = await sql(dbh, """
                SELECT content
                  FROM testsources
                 WHERE testsource_id = %s
                """, [self.testsource_id])
        return ret[0].content

    async def metadata(self, dbh):
        rows = await sql(dbh, """
            SELECT testsource_id,
                   testsources.filename,
                   testsources.project_id,
                   COALESCE(testsources.apk_id, '') AS apk_id,
                   testsources.status,
                   COALESCE(project_apks.status, '') AS apk_status,
                   COALESCE(project_apks.status_reason, '') AS apk_status_reason
              FROM testsources
         LEFT JOIN project_apks
                ON project_apks.apk_id = testsources.apk_id
             WHERE testsource_id = %s
                """, [self.testsource_id])

        if not rows:
            return None

        return rows[0]._asdict()

    async def delete(self, dbh):
        await sql(dbh, """
            DELETE FROM testsources
                  WHERE testsource_id = %s
            """, [self.testsource_id])

    async def apk_id(self, dbh):
        ret = await sql(dbh, """
            SELECT apk_id
              FROM testsources
             WHERE testsource_id = %s
            """, [self.testsource_id])
        return ret[0].apk_id

    async def filename(self, dbh):
        ret = await sql(dbh, """
            SELECT filename
              FROM testsources
             WHERE testsource_id = %s
            """, [self.testsource_id])
        return ret[0].filename

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE testsources
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE testsource_id = %s
            """, [status, reason, self.testsource_id])

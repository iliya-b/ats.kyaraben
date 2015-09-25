
from ats.util.db import sql, asdicts


class Camera:
    def __init__(self, *, camera_id):
        self.camera_id = camera_id

    @classmethod
    async def is_deleted(self, dbh, *, camera_id):
        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM project_camera
             WHERE camera_id = %s
                   AND status = 'DELETED'
            """, [camera_id])

        return len(rows)

    @classmethod
    async def get(cls, dbh, *, camera_id, project_id, userid):
        """
        Async method to check for existence, which can't be done in __init__.
        """

        rows = await sql(dbh, """
            SELECT 1 AS dummy
              FROM project_camera
             WHERE camera_id = %s
                   AND project_id = %s
                   AND status <> 'DELETED'
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [camera_id, project_id, userid])

        if len(rows):
            return cls(camera_id=camera_id)
        else:
            return None

    @classmethod
    async def insert(cls, dbh, *, camera_id, filename, project_id):
        await sql(dbh, """
            INSERT INTO project_camera (
                    camera_id, filename, project_id
                ) VALUES (%s, %s, %s)
            """, [camera_id, filename, project_id])

    @classmethod
    async def list(cls, dbh, *, userid, project_id):
        rows = await sql(dbh, """
            SELECT camera_id,
                   filename,
                   project_id,
                   status
              FROM project_camera
             WHERE project_id = %s
                   AND status <> 'DELETED'
                   AND project_id IN (SELECT project_id FROM permission_projects WHERE userid = %s)
            """, [project_id, userid])

        return asdicts(rows)

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE project_camera
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE camera_id = %s
            """, [status, reason, self.camera_id])

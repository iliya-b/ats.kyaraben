
from ats.util.db import sql


class Command:
    def __init__(self, *, command_id):
        self.command_id = command_id

    async def set_status(self, dbh, status, reason=''):
        await sql(dbh, """
            UPDATE avm_commands
               SET status = %s,
                   status_ts = transaction_timestamp(),
                   status_reason = %s
             WHERE command_id = %s
            """, [status, reason, self.command_id])

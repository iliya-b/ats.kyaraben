
from pathlib import Path
import pkg_resources
import psycopg2
import re
from textwrap import dedent

import structlog


class DatabaseError(Exception):
    pass


# This schema upgrade mechanism is simplistic and doesn't work well with code merges.
# Alembic would be better though more complex.


schema_version_table = dedent("""
    CREATE TABLE IF NOT EXISTS schema_version (
        singleton INTEGER DEFAULT 0 PRIMARY KEY CHECK (singleton=0),
        version INTEGER DEFAULT 0
    );
    INSERT INTO schema_version SELECT 0, 0 WHERE NOT EXISTS (SELECT * FROM schema_version);
""")


def fetch_scripts():
    sql_dir = Path(pkg_resources.resource_filename('ats.kyaraben.server', 'db'), 'scripts')
    renum = re.compile('\d+')

    return {
        int(renum.match(script.name).group()): script
        for script in sorted(sql_dir.glob('*.sql'))
    }


async def db_update(pool):
    log = structlog.get_logger()

    scripts = fetch_scripts()

    with (await pool.cursor()) as cur:
        await cur.execute('BEGIN')
        await cur.execute(schema_version_table)
        await cur.execute('SELECT version FROM schema_version')
        current_version = (await cur.fetchone())[0]

        while max(scripts) > current_version:
            current_version += 1
            try:
                script = scripts[current_version]
            except KeyError:
                raise DatabaseError('Missing migration script %d' % current_version) from None

            log.info('Applying %s', script.name)
            with script.open(encoding='utf8') as fin:
                query = fin.read()
                if not query.strip():
                    log.info('Empty query.')
                    continue
                await cur.execute(query)

            await cur.execute('UPDATE schema_version SET version=%s', [current_version])
        await cur.execute('COMMIT')


async def db_require_latest_version(pool):
    scripts = fetch_scripts()
    with (await pool.cursor()) as cur:
        try:
            await cur.execute('SELECT COALESCE(version, -1) FROM schema_version')
        except psycopg2.ProgrammingError:
            raise DatabaseError('Database schema has not been initialized. '
                                'Please run again with --db-update') from None
        current_version = (await cur.fetchone())[0]
        required_version = max(scripts)
        if current_version < required_version:
            raise DatabaseError('Database schema is at version %d, but version %d is required. '
                                'Please run again with --db-update' % (current_version, required_version)) from None
        if current_version > required_version:
            raise DatabaseError('Database schema is at version %s, which is unsupported. '
                                'Please upgrade the application.' % current_version) from None

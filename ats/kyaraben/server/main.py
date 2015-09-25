
import argparse
import asyncio
import os
import sys
import warnings

import aiopg
import psycopg2.extras
import structlog

from ats.kyaraben.config import config_get, ConfigPrinter
from ats.kyaraben.docker import cmd_docker_compose
from ats.util.logging import setup_logging, setup_structlog, structlog_middleware

from .app import KyarabenApp
from .db import schema

psycopg2.extras.register_uuid()
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('error', 'coroutine .* was never awaited.*', category=RuntimeWarning)


async def restart_xtext():
    log = structlog.get_logger()
    log.info('Restarting Xtext:')
    await cmd_docker_compose('-f', 'run-xtext.yml', 'down', log=log)
    await cmd_docker_compose('-f', 'run-xtext.yml', 'up',
                             '--no-color', '--no-build', '-d', log=log)
    log.info('..done.')


async def init(*, loop, config, debug=False):
    log = structlog.get_logger()

    app = KyarabenApp(config=config,
                      loop=loop,
                      logger=log,
                      middlewares=[structlog_middleware])
    await app.setup()

    listen_address = app.config['server']['listen_address'].strip()

    if debug:
        import aiohttp_debugtoolbar
        aiohttp_debugtoolbar.setup(app, hosts=[listen_address])
        log.info('Debug toolbar available at /_debugtoolbar')

    listen_port = app.config['server']['listen_port']

    srv = await loop.create_server(app.make_handler(),
                                   listen_address,
                                   listen_port)
    for socket in srv.sockets:
        log.info('Server started at %s', socket.getsockname())
    return srv


def get_parser():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        '--write-config-defaults',
        action=ConfigPrinter(),
        nargs=0,
        help='print default configuration values')

    ap.add_argument(
        '--debug',
        dest='debug',
        action='store_true',
        help='enable debug toolbar')

    ap.add_argument(
        '--no-debug',
        dest='debug',
        action='store_false',
        help='disable debug toolbar')

    ap.add_argument(
        '--db-update',
        action='store_true',
        help='Update the database schema')

    ap.set_defaults(debug=False)

    return ap


def main(argv=sys.argv[1:]):
    parser = get_parser()
    args = parser.parse_args(argv)

    config = config_get(environ=os.environ)
    setup_logging(config)
    setup_structlog(config,
                    key_order=['delivery_tag', 'task'])

    loop = asyncio.get_event_loop()
    # asyncio debugging
    loop.set_debug(enabled=False)

    pool = loop.run_until_complete(aiopg.create_pool(config['db']['dsn']))

    if args.db_update:
        loop.run_until_complete(schema.db_update(pool))

    loop.run_until_complete(schema.db_require_latest_version(pool))
    loop.run_until_complete(restart_xtext())
    loop.run_until_complete(init(loop=loop, config=config, debug=args.debug))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

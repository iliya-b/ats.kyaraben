
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import traceback
import warnings

import aiopg
import psycopg2.extras
import structlog

from ats.kyaraben.config import config_get
from ats.util.logging import setup_logging, setup_structlog
from ats.kyaraben.tasks import TaskBroker, ConnectionFactory
from ats.kyaraben.worker.task_errors import set_status_error, is_task_obsolete
from ats.kyaraben.worker.openstack.exceptions import OSHeatError, AVMNotFoundError, AVMImageNotFoundError

from . import tasks
from .amqp.admin import AMQPAdminGateway
from .openstack.gateway import OpenStackGateway
from .openstack.heatclient import HeatClient


psycopg2.extras.register_uuid()
# this definitely indicates a bug that must be fixed
warnings.filterwarnings('error', 'coroutine .* was never awaited.*', category=RuntimeWarning)


async def handle_message(app, log, channel, msg, envelope, properties):
    task = properties.headers['x-kyaraben-task']
    log = log.bind(task=task)
    try:
        handler = {
            'project_container_create': tasks.project_container_create,
            'project_container_delete': tasks.project_container_delete,
            'avm_create': tasks.avm_create,
            'avm_containers_create': tasks.avm_containers_create,
            'avm_delete': tasks.avm_delete,
            'avm_monkey': tasks.avm_monkey,
            'avm_test_run': tasks.avm_test_run,
            'camera_upload': tasks.camera_upload,
            'camera_delete': tasks.camera_delete,
            'apk_upload': tasks.apk_upload,
            'apk_delete': tasks.apk_delete,
            'apk_install': tasks.apk_install,
            'testsource_compile': tasks.testsource_compile,
            'campaign_run': tasks.campaign_run,
            'campaign_avm_create': tasks.campaign_avm_create,
            'campaign_containers_create': tasks.campaign_containers_create,
            'campaign_runtest': tasks.campaign_runtest,
            'campaign_delete': tasks.campaign_delete,
        }[task]
    except KeyError:
        log.error('unknown task')
        raise

    if await is_task_obsolete(app, **msg):
        log.warning('task is obsolete')
        return

    exception = None
    reason = ''

    try:
        await handler(app=app, log=log, **msg)
    except tasks.TaskDelay as exc:
        reason = exc.args[0]
        delay_msecs = None
        if delay_msecs is None:
            delay_msecs = app.config['worker']['heat_poll_interval'] * 1000
        log.debug('republishing message', delay_msecs=delay_msecs, reason=reason)
        await app.task_broker.publish(task, msg, delay=delay_msecs, log=log)
    except OSHeatError as exc:
        exception = traceback.format_exc()
        if isinstance(exc, AVMImageNotFoundError):
            reason = 'Image {[image]} not found'.format(msg)
        if isinstance(exc, AVMNotFoundError):
            reason = 'VM {[avm_id]} not found'.format(msg)
    except Exception:
        exception = traceback.format_exc()

    # Exceptions caught here and not re-raised are permanent.
    # Raising from handle_message() sends a nack to the dead-letter exchange, if defined.

    if exception:
        log.error(message_id=properties.message_id,
                  message_ts=properties.timestamp,
                  message_headers=properties.headers,
                  message=msg,
                  exception=exception)

        await set_status_error(app, log, reason=reason, message=msg)


class App:
    def __init__(self, *, config, args, loop):
        self.config = config
        self.args = args
        self.loop = loop
        self.log = structlog.get_logger()
        self.dbpool = None
        osgw = OpenStackGateway(config_os=config['openstack'], logger=self.log)
        self.heat = HeatClient(osgw, config)
        self.task_broker = None
        self.amqp_admin = None
        self.done_tasks = 0

    async def setup(self):
        self.dbpool = await aiopg.create_pool(self.config['db']['dsn'])
        self.amqp_connection_factory = ConnectionFactory(host=self.config['amqp']['hostname'],
                                                         login=self.config['amqp']['admin_username'],
                                                         password=self.config['amqp']['admin_password'])
        self.task_broker = TaskBroker(self.amqp_connection_factory)
        await self.task_broker.setup()
        await self.setup_amqp_admin()

    async def camera_path(self, *, camera_id):
        path_tpl = self.config['prjdata']['camera_path']
        return Path(path_tpl.format(camera_id=camera_id)).as_posix()

    async def apk_path(self, *, apk_id):
        path_tpl = self.config['prjdata']['apk_path']
        return Path(path_tpl.format(apk_id=apk_id)).as_posix()

    async def setup_amqp_admin(self):
        self.amqp_admin = AMQPAdminGateway(config_amqp=self.config['amqp'], logger=self.log)
        transport, protocol = await self.amqp_connection_factory()
        channel = await protocol.channel()
        await channel.exchange_declare(exchange_name='android-events',
                                       type_name='topic',
                                       durable=True,
                                       auto_delete=False)

    async def consume(self, channel, body, envelope, properties):
        try:
            log = self.log.bind(delivery_tag=envelope.delivery_tag, message_id=properties.message_id)
            payload = body.decode('utf8')
            if properties.message_id in self.args.reject:
                log.debug('reject messages')
                await channel.basic_client_nack(delivery_tag=envelope.delivery_tag, multiple=False, requeue=False)
            else:
                log.debug('got message', message_id=properties.message_id, payload=payload)
                js = json.loads(payload)
                await handle_message(self, log, channel, js, envelope, properties)
                log.info('message acknowledged')
                await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
                self.done_tasks += 1
        except Exception:
            log.exception()
            log.warning('message rejected upon task failure', message_id=properties.message_id)
            await channel.basic_client_nack(delivery_tag=envelope.delivery_tag, multiple=False, requeue=False)

        if self.args.tasks:
            log.new().warning('%s of %s task%s processed',
                              self.done_tasks,
                              self.args.tasks,
                              ['', 's'][self.done_tasks != 1])
            if self.done_tasks >= self.args.tasks:
                self.loop.stop()
                # If we were using threads:
                # loop.call_soon_threadsafe(loop.stop)

    async def run(self):
        self.log.info('waiting for messages')
        await self.task_broker.consume(callback=self.consume)


async def init(*, loop, config, args):
    app = App(config=config, args=args, loop=loop)
    await app.setup()
    await app.run()


def get_parser():
    ap = argparse.ArgumentParser()

    ap.add_argument('--reject',
                    help='Reject message',
                    nargs='*',
                    default=[])

    ap.add_argument('--tasks',
                    help='Perform a given number of tasks, then quit (0 = loop forever)',
                    type=int,
                    default=0)

    return ap


def main(argv=sys.argv[1:]):
    config = config_get(environ=os.environ)
    setup_logging(config)
    setup_structlog(config,
                    key_order=['uid', 'project', 'project_id', 'avm'])

    loop = asyncio.get_event_loop()
    # asyncio debugging
    loop.set_debug(enabled=False)

    parser = get_parser()
    args = parser.parse_args(argv)

    loop.run_until_complete(init(loop=loop, config=config, args=args))

    try:
        loop.run_forever()
        loop.close()
    except KeyboardInterrupt:
        pass


import argparse
import asyncio
import os
import sys
import time
import warnings

import psycopg2.extras
import structlog

from ats.kyaraben.config import config_get
from ats.util.logging import setup_logging, setup_structlog
from ats.kyaraben.tasks import ConnectionFactory
from ats.kyaraben.lock import get_lock

psycopg2.extras.register_uuid()
# this definitely indicates a bug that must be fixed
warnings.filterwarnings('error', 'coroutine .* was never awaited.*', category=RuntimeWarning)


class TaskCollector:
    def __init__(self, connection_factory, delay_min, delay_max):
        self.connection_factory = connection_factory
        self.delay_min_ms = delay_min * 1000
        self.delay_max_ms = delay_max * 1000

    async def setup(self):
        transport, protocol = await self.connection_factory()
        self.publish_channel = await protocol.channel()
        self.consume_channel = await protocol.channel()
        await self.publish_channel.exchange_declare(exchange_name='orchestration.retry',
                                                    type_name='direct',
                                                    durable=True,
                                                    auto_delete=False)
        await self.publish_channel.exchange_declare(exchange_name='orchestration.failed',
                                                    type_name='direct',
                                                    durable=True,
                                                    auto_delete=False)
        await self.consume_channel.basic_qos(prefetch_count=1,
                                             prefetch_size=0,
                                             connection_global=False)
        await self.consume_channel.queue_declare(queue_name='orchestration.retry',
                                                 durable=True,
                                                 exclusive=False,
                                                 arguments={
                                                     'x-dead-letter-exchange': 'orchestration.failed'
                                                 })
        await self.consume_channel.queue_bind(queue_name='orchestration.retry',
                                              exchange_name='orchestration.retry',
                                              routing_key='orchestration')
        await self.consume_channel.queue_declare(queue_name='orchestration.failed',
                                                 durable=True,
                                                 exclusive=False)
        await self.consume_channel.queue_bind(queue_name='orchestration.failed',
                                              exchange_name='orchestration.failed',
                                              routing_key='orchestration')

    async def repost(self, body, properties, log):
        headers = properties.headers
        retries = headers.get('x-kyaraben-retries', 0) + 1
        headers['x-delay'] = min(self.delay_max_ms, int(self.delay_min_ms * 1.5 ** retries))
        headers['x-kyaraben-retries'] = retries
        log.info('repost task with delay %s msecs', headers['x-delay'])
        death = headers.pop('x-death')[0]
        properties = {
            'message_id': properties.message_id,
            'timestamp': properties.timestamp,
            'content_type': properties.content_type,
            'delivery_mode': properties.delivery_mode,
            'headers': properties.headers,
        }
        await self.publish_channel.publish(payload=body,
                                           exchange_name=death['exchange'],
                                           properties=properties,
                                           routing_key=death['routing-keys'][0])

    async def consume(self, callback):
        await self.consume_channel.basic_consume(callback,
                                                 queue_name='orchestration.retry',
                                                 no_ack=False)


class App:
    def __init__(self, config, args, loop):
        self.config = config
        self.args = args
        self.loop = loop
        self.log = structlog.get_logger()
        self.task_collector = None

    async def setup(self):
        self.amqp_connection_factory = ConnectionFactory(host=self.config['amqp']['hostname'],
                                                         login=self.config['amqp']['admin_username'],
                                                         password=self.config['amqp']['admin_password'])
        self.task_collector = TaskCollector(self.amqp_connection_factory,
                                            delay_min=self.config['retry']['delay_min'],
                                            delay_max=self.config['retry']['delay_max'])
        await self.task_collector.setup()

    async def consume(self, channel, body, envelope, properties):
        try:
            log = self.log.bind(delivery_tag=envelope.delivery_tag, message_id=properties.message_id)
            if time.time() - properties.timestamp > self.config['retry']['fail_timeout']:
                log.warning('message discarded (fail timeout)')
                await channel.basic_client_nack(delivery_tag=envelope.delivery_tag, multiple=False, requeue=False)
            else:
                log.debug('got message', headers=properties.headers, body=body.decode('utf8'))
                await self.task_collector.repost(body, properties, log=log)
                await channel.basic_client_ack(delivery_tag=envelope.delivery_tag)
        except Exception:
            log.exception()
            raise

    async def run(self):
        self.log.info('waiting for messages')
        await self.task_collector.consume(callback=self.consume)


async def init(loop, config, args):
    app = App(config=config, args=args, loop=loop)
    await app.setup()
    await app.run()


def get_parser():
    ap = argparse.ArgumentParser()
    return ap


def main(argv=sys.argv[1:]):
    config = config_get(environ=os.environ)
    setup_logging(config)
    setup_structlog(config)

    loop = asyncio.get_event_loop()
    # asyncio debugging
    loop.set_debug(enabled=False)

    parser = get_parser()
    args = parser.parse_args(argv)

    loop.run_until_complete(init(loop=loop, config=config, args=args))

    with get_lock('retry', log=structlog.get_logger()):
        try:
            loop.run_forever()
            loop.close()
        except KeyboardInterrupt:
            pass

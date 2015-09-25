
import json
import time
import uuid

import aioamqp
import structlog


class ConnectionFactory:
    def __init__(self, host, login, password):
        self.host = host
        self.login = login
        self.password = password
        self.port = 5672
        self.virtualhost = '/'

    async def __call__(self):
        try:
            transport, protocol = await aioamqp.connect(
                host=self.host,
                port=self.port,
                login=self.login,
                password=self.password,
                virtualhost=self.virtualhost)
        except ConnectionRefusedError:
            log = structlog.get_logger()
            log.error('Cannot connect to RabbitMQ server at amqp://%s:%s', self.host, self.port)
            raise

        return transport, protocol


class TaskBroker:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    async def setup(self):
        transport, protocol = await self.connection_factory()
        self.publish_channel = await protocol.channel()
        self.consume_channel = await protocol.channel()
        await self.publish_channel.exchange_declare(exchange_name='orchestration',
                                                    type_name='x-delayed-message',
                                                    durable=True,
                                                    auto_delete=False,
                                                    arguments={
                                                        'x-delayed-type': 'direct'
                                                    })
        await self.consume_channel.basic_qos(prefetch_count=1,
                                             prefetch_size=0,
                                             connection_global=False)
        await self.consume_channel.queue_declare(queue_name='orchestration',
                                                 durable=True,
                                                 exclusive=False,
                                                 arguments={
                                                     'x-dead-letter-exchange': 'orchestration.retry'
                                                 })
        await self.consume_channel.queue_bind(queue_name='orchestration',
                                              exchange_name='orchestration',
                                              routing_key='orchestration')

    async def publish(self, task_name, msg, log, delay=0):
        properties = {
            'message_id': uuid.uuid1().hex,
            'timestamp': int(time.time()),
            'content_type': 'application/json',
            'delivery_mode': 2,
            'headers': {
                'x-kyaraben-task': task_name
            }
        }
        if delay:
            properties['headers']['x-delay'] = delay
        log.info('publish task', msg, properties=properties)
        await self.publish_channel.publish(payload=json.dumps(msg),
                                           exchange_name='orchestration',
                                           properties=properties,
                                           routing_key='orchestration')

    async def consume(self, callback):
        await self.consume_channel.basic_consume(callback,
                                                 queue_name='orchestration',
                                                 no_ack=False)

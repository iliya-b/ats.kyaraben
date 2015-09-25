"""

Provide functions to update the RabbitMQ configuration
when creating and destroying AVMs.

"""


def queues_routing(avm_id):
    for shortname in ['sensors', 'battery', 'gps', 'recording', 'gsm', 'camera', 'nfc']:
        queue_tpl = 'android-events.{avm_id}.{shortname}'

        if shortname == 'sensors':
            routing_tpl = 'android-events.{avm_id}.{shortname}.*'
        else:
            routing_tpl = 'android-events.{avm_id}.{shortname}'

        d = {'avm_id': avm_id, 'shortname': shortname}
        yield queue_tpl.format(**d), routing_tpl.format(**d)


async def create_event_queues(app, log, *, avm_id):
    """
    Create exchange and queues for an AVM
    """
    transport, protocol = await app.amqp_connection_factory()
    channel = await protocol.channel()
    log.debug('Creating event queues', avm_id=avm_id)
    for queue_name, routing_key in queues_routing(avm_id):
        log.debug(queue_name=queue_name, routing_key=routing_key)
        await channel.queue_declare(queue_name=queue_name,
                                    durable=True,
                                    auto_delete=False)
        await channel.queue_bind(queue_name=queue_name,
                                 exchange_name='android-events',
                                 routing_key=routing_key)

async def delete_event_queues(app, log, *, avm_id):
    """
    Remove exchange and queues for an AVM
    """
    # it should remove all the queues that start with avm_id
    # just in case some queue names were removed in a new version
    # of the service, but listing them requires admin API

    transport, protocol = await app.amqp_connection_factory()
    channel = await protocol.channel()
    log.debug('Removing event queues', avm_id=avm_id)
    for queue_name, _ in queues_routing(avm_id):
        await channel.queue_delete(queue_name)

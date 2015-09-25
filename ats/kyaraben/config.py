
from ats.util.options import Option, get_configdict, EnvConfigPrinter


prefix = 'KYARABEN_'

options = [
    Option('server.listen_address', default='127.0.0.1'),
    Option('server.listen_port', default=8084),
    Option('log.jsonformat', default=False,
           help='Write log lines as JSON objects'),
    Option('amqp.hostname', default='127.0.0.1'),
    Option('amqp.admin_username', default='guest'),
    Option('amqp.admin_password', default='guest'),
    Option('orchestration.novnc_host',
           required=True,
           help='IP address/hostname of the player containers'),
    Option('orchestration.stackprefix', default=''),
    Option('openstack.os_auth_url', required=True),
    Option('openstack.insecure', default=False, required=False,
           help='Do not verify SSL certificate'),
    Option('openstack.os_cacert', required=False),
    Option('openstack.os_tenant_name'),
    Option('openstack.os_username'),
    Option('openstack.os_password'),
    Option('openstack.floating_net', default='net04_ext'),
    Option('docker.host'),
    Option('docker.tls_verify', default=True),
    Option('db.dsn'),
    Option('quota.vm_async_max', default=1),
    Option('quota.vm_live_max', default=3),
    Option('openstack.template', default='android.yaml'),
    Option('worker.heat_poll_interval', default=5),
    Option('retry.delay_min', default=1,
           help='initial delay between retries'),
    Option('retry.delay_max', default=30,
           help='max delay between retries'),
    Option('retry.fail_timeout', default=60 * 60 * 24,
           help='after 24h, failed messages will be discarted'),
    Option('media.tempdir', default='/tmp'),
    Option('prjdata.apk_path', default='/data/project/apk/{apk_id}.apk'),
    Option('prjdata.camera_path', default='/data/project/camera/{camera_id}'),
]


def config_get(environ):
    return get_configdict(prefix=prefix,
                          options=options,
                          environ=environ)


def ConfigPrinter():
    return EnvConfigPrinter(prefix=prefix,
                            options=options)

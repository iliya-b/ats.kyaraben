from http import HTTPStatus
import json
import urllib.parse

import aiohttp

from ats.kyaraben.url import urlpath


header_json_content = ('Content-Type', 'application/json')


class AMQPRestError(Exception):
    def __init__(self, status, reason, *args):
        message = '%s (%s): %s' % (status, HTTPStatus(status).name, reason)
        super().__init__(message, *args)


def get_session():
    return aiohttp.ClientSession(connector=aiohttp.TCPConnector())


class AMQPAdminGateway:
    def __init__(self, config_amqp, logger):
        self._hostname = config_amqp['hostname']
        self._admin_username = config_amqp['admin_username']
        self._admin_password = config_amqp['admin_password']
        self.log = logger
        self.session = get_session()

    @property
    def auth(self):
        return aiohttp.BasicAuth(self._admin_username,
                                 password=self._admin_password)

    async def _request(self, method, path, data, headers):
        # copy to avoid modifying the caller's namespace
        headers = list(headers)

        url = urlpath('http://%s:15672/' % self._hostname, 'api', *path)
        return await getattr(self.session, method)(
            url,
            data=data,
            headers=headers + [header_json_content],
            auth=self.auth)

    async def __call__(self, method, path, data=None, headers=None):
        if headers is None:
            headers = []

        r = await self._request(method, path, data, headers)

        if r.status == HTTPStatus.UNAUTHORIZED:
            self.log.warning('Unable to authenticate.')

        return r

    async def create_user(self, username, password):
        js = {'password': password, 'tags': ''}
        self.log.debug('Creating RabbitMQ user', username=username)

        res = await self('put', ['users', username], json.dumps(js))
        if res.status != HTTPStatus.NO_CONTENT:
            error = await res.json()
            raise AMQPRestError(res.status, error['reason'])

    async def delete_user(self, username):
        res = await self('delete', ['users', username], '')
        if res.status != HTTPStatus.NO_CONTENT:
            error = await res.json()
            raise AMQPRestError(res.status, error['reason'])

    async def set_user_permissions(self, vhost, username, avm_id):
        js = {
            "configure": "",
            "write": "",
            "read": "android-events.{}.*".format(avm_id)
        }
        quoted_vhost = urllib.parse.quote_plus(vhost)
        res = await self('put', ['permissions', quoted_vhost, username], json.dumps(js))
        if res.status != HTTPStatus.NO_CONTENT:
            error = await res.json()
            raise AMQPRestError(res.status, error['reason'])


from http import HTTPStatus
import json

from ats.util.helpers import get_os_session
from ats.kyaraben.url import urlpath


header_json_content = ('Content-Type', 'application/json')


class OpenStackGateway:
    """
    A wrapper to API calls that automatically re-authenticates when the
    token has expired.
    """

    def __init__(self, config_os, logger):
        self.os_auth_url = config_os['os_auth_url']
        self.os_tenant_name = config_os['os_tenant_name']
        self.os_username = config_os['os_username']
        self.os_password = config_os['os_password']
        self.logger = logger
        self.session = get_os_session(os_cacert=config_os.get('os_cacert'),
                                      insecure=config_os.get('insecure'),
                                      log=logger)

    @property
    def auth_payload(self):
        return {
            'auth': {
                'identity':{
                    'methods':['password'],
                    'password':{
                        'user':{
                            'domain':{'name':'Default'},
                            'name': self.os_username,
                            'password': self.os_password
                        }
                    }
                }
            }
        }

    async def get_catalog(self, token_id):
        r = await self.session.post(self.os_auth_url + '/catalog',
                                    data=json.dumps(self.auth_payload),
                                    headers=[header_json_content ] + ('X-Auth-Token', token_id))
        js = await r.json()

        if r.status >= 300:
            self.logger.error('HTTP error: %s' % js)
            for line in repr(r).split('\n'):
                if line:
                    self.logger.error(line)
            raise Exception('Error while authenticating with OpenStack')
        
        return js

    async def new_auth(self):
        r = await self.session.post(self.os_auth_url + '/tokens',
                                    data=json.dumps(self.auth_payload),
                                    headers=[header_json_content])
        js = await r.json()

        if r.status >= 300:
            self.logger.error('HTTP error: %s' % js)
            for line in repr(r).split('\n'):
                if line:
                    self.logger.error(line)
            raise Exception('Error while authenticating with OpenStack')
        token_id = r.headers['x-subject-token']
        return {
            'token_id': token_id, #js['access']['token']['id'],
            'endpoints': {
                 service['name']: service['endpoints'][0]['url']
                 for service in (await self.get_catalog(token_id))['catalog']
             }
        }

    async def _request(self, service, method, auth, path, data, headers):
        # copy to avoid modifying the caller's namespace
        headers = list(headers)
        header_auth_token = ('X-Auth-Token', auth['token_id'])

        url = urlpath(auth['endpoints'][service], *path)
        return await getattr(self.session, method)(
            url,
            data=data,
            headers=headers + [header_auth_token])

    async def __call__(self, service, method, path, data=None, headers=None):
        if headers is None:
            headers = []

        auth = await self.new_auth()
        r = await self._request(service, method, auth, path, data, headers)

        return r

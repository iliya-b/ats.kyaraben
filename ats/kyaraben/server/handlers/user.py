
from aiohttp import web

from ats.util.db import sql
from ats.util.helpers import authenticated_userid


class UserHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/user/quota', self.quota)
        router.add_route('GET', '/user/whoami', self.whoami)

    async def quota(self, request):
        config = request.app.config

        userid = await authenticated_userid(request)

        request['slog'].debug('Querying user quota')

        rows = await sql(request, """
            SELECT live_current, async_current
              FROM quota_usage
             WHERE uid_owner = %s
            """, [userid])

        live_current = rows and rows[0].live_current or 0
        async_current = rows and rows[0].async_current or 0

        response_js = {
            'quota': {
                'vm_live_max': config['quota']['vm_live_max'],
                'vm_live_current': live_current,
                'vm_async_max': config['quota']['vm_async_max'],
                'vm_async_current': async_current,
            }
        }

        return web.json_response(response_js)

    async def whoami(self, request):
        config = request.app.config

        userid = await authenticated_userid(request)

        response_js = {
            'user': {
                'userid': userid,
            }
        }

        return web.json_response(response_js)

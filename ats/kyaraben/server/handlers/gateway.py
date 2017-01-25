
from aiohttp import web

from ats.kyaraben.docker import cmd_docker_inspect
from ats.util.logging import nullog


async def inspect_port(container, port):
    fmt = '{{(index (index .NetworkSettings.Ports "%s") 0).HostPort}}' % port
    proc = await cmd_docker_inspect('--format', fmt, container, log=nullog)
    return proc.out


class GatewayHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/gateway/android/{avm_id}/ports', self.ports)

    async def ports(self, request):
        avm_id = request.match_info['avm_id']

        log = request['slog']
        log.debug('Port inspection requested')

        screen_port = await inspect_port('%s_xorg' % avm_id, '5900/tcp')
        sound_port = await inspect_port('%s_ffserver' % avm_id, '8090/tcp')
        host = request.app.config['orchestration']['novnc_host']

        response_js = {
            'avm': {
                'avm_id': avm_id,
                'host': host,
                'screen_port': screen_port,
                'sound_port': sound_port,
            }
        }

        return web.json_response(response_js)

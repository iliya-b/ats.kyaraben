
import datetime
from http import HTTPStatus
import re
import uuid

from aiohttp import web
from oath import totp

from ats.kyaraben.docker import cmd_docker_exec
from ats.kyaraben.model.android import AndroidVM
from ats.kyaraben.model.apk import APK
from ats.kyaraben.password import generate_password
from ats.kyaraben.process import ProcessError
from ats.util.helpers import authenticated_userid, json_request
from ats.util.db import sql
from ats.util.logging import nullog


class AndroidHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/android', self.list)
        router.add_route('GET', '/android/{avm_id}', self.show)
        router.add_route('GET', '/android/{avm_id}/properties', self.properties)
        router.add_route('GET', '/android/{avm_id}/totp', self.get_totp)
        router.add_route('POST', '/android/{avm_id}/monkey', self.monkey)
        router.add_route('GET', '/android/{avm_id}/command/{command_id}', self.command_status)
        router.add_route('POST', '/android/{avm_id}/testrun', self.test_run)
        router.add_route('GET', '/android/{avm_id}/testrun', self.test_list)
        router.add_route('POST', '/android', self.create)
        router.add_route('PUT', '/android/{avm_id}', self.update)
        router.add_route('DELETE', '/android/{avm_id}', self.delete)
        router.add_route('GET', '/android/{avm_id}/apk', self.apk_list)
        router.add_route('POST', '/android/{avm_id}/apk/{apk_id}', self.apk_install)

    async def list(self, request):
        """
        List all the Android VMs that belong to a user.
        """
        userid = await authenticated_userid(request)

        request['slog'].debug('Retrieving AVM list')

        project_id = request.GET.get('project_id')

        response_js = {
            'avms': await AndroidVM.list(request,
                                         userid=userid,
                                         project_id=project_id)
        }

        return web.json_response(response_js)

    async def show(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        response_js = {
            'avm': await avm.select(request)
        }

        return web.json_response(response_js)

    async def create(self, request):
        """
        Create an Android VM and related services.
        """

        request_schema = {
            'type': 'object',
            'properties': {
                'project_id': {'type': 'string'},
                'image': {'type': 'string'},
                'avm_name': {'type': 'string'},
                'hwconfig': {
                    'type': 'object',
                    'properties': {
                        'width': {'type': 'integer', 'minimum': 240},
                        'height': {'type': 'integer', 'minimum': 240},
                        'dpi': {'type': 'integer', 'minimum': 100},
                        'enable_sensors': {'type': 'integer'},
                        'enable_battery': {'type': 'integer'},
                        'enable_gps': {'type': 'integer'},
                        'enable_camera': {'type': 'integer'},
                        'enable_record': {'type': 'integer'},
                        'enable_gsm': {'type': 'integer'},
                        'enable_nfc': {'type': 'integer'},
                    }
                },
            },
            'required': ['project_id', 'image']
        }

        config = request.app.config

        userid = await authenticated_userid(request)

        js = await json_request(request, schema=request_schema)

        hwconfig = {**AndroidVM.hwconfig_defaults, **js.get('hwconfig', {})}

        log = request['slog']
        log.debug('Android VM creation requested', body=js)

        # check that project exists, and have permission

        project = await request.app.context_project(request,
                                                    userid=userid,
                                                    project_id=js['project_id'])

        # check quota

        vm_per_user = config['quota']['vm_live_max']

        live_current = (await AndroidVM.count(request, uid_owner=userid))['live_current']

        log.debug('VM count', live_vms=live_current)

        if vm_per_user and live_current >= vm_per_user:
            raise web.HTTPBadRequest(text='Too many vms, max allowed is %d' % vm_per_user)

        avm_id = uuid.uuid1().hex
        avm_name = js.get('avm_name', None)

        # check that image exists

        image = js['image']
        rows = await sql(request, "SELECT 1 AS dummy FROM images WHERE image = %s", [image])

        if not rows:
            raise web.HTTPNotFound(text='Image %s not found' % image)

        vnc_secret = generate_password(128, password_chars='01234567890abcdef')

        await AndroidVM.insert(request,
                               avm_id=avm_id,
                               avm_name=avm_name,
                               userid=userid,
                               project_id=project.project_id,
                               image=image,
                               hwconfig=hwconfig,
                               testrun_id=None,
                               vnc_secret=vnc_secret)

        await request.app.task_broker.publish('avm_create', {
            'userid': userid,
            'image': image,
            'project_id': project.project_id,
            'avm_id': avm_id,
            'hwconfig': hwconfig,
            'vnc_secret': vnc_secret,
        }, log=log)

        response_js = {
            'avm_id': avm_id
        }

        return web.json_response(response_js, status=HTTPStatus.CREATED)

    async def update(self, request):
        """
        Update a vm's data
        """

        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        js = await json_request(request)
        avm_name = js['avm_name']

        request['slog'].debug('request: avm update', body=js)
        await avm.update(request, avm_name=avm_name)

        return web.HTTPNoContent()

    async def get_totp(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        rows = await sql(request, """
            SELECT vnc_secret
              FROM avmotp
             WHERE avmotp.avm_id = %s
            """, [avm.avm_id])

        secret = rows[0][0]

        response_js = {
            'totp': totp(secret)
        }

        return web.json_response(response_js)

    async def delete(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        log = request['slog']
        log.debug('request: android delete')

        stack_name = await avm.get_stack_name(request)
        if stack_name is None:
            raise web.HTTPNotFound()

        await request.app.task_broker.publish('avm_delete', {
            'userid': userid,
            'avm_id': avm.avm_id,
            'stack_name': stack_name,
        }, log=log)

        await avm.set_status(request, status='DELETING')

        return web.HTTPAccepted()

    _re_parse_property = re.compile('\[(?P<key>[a-zA-Z0-9\-\.\_]+)\]\s*:\s+\[(?P<value>.*)\]')

    def _parse_properties(self, lines, log):
        ret = {}
        for line in lines:
            m = self._re_parse_property.match(line)
            if not m:
                log.warning('Property line does not match: %s', line)
                continue
            ret[m.group('key')] = m.group('value')
        return ret

    async def properties(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        log = request['slog']
        log.debug('Property list requested')

        try:
            proc = await cmd_docker_exec('{.avm_id}_adb'.format(avm),
                                         'adb', 'shell', 'getprop', log=nullog)
            properties = self._parse_properties(proc.out_lines, log=log)
        except ProcessError:
            properties = {}

        return web.json_response({'properties': properties})

    async def _bootcomplete(self, avm, *, log):
        # or sys.boot_completed, should be the same
        proc = await cmd_docker_exec('{.avm_id}_adb'.format(avm),
                                     'adb', 'shell', 'getprop', 'dev.bootcomplete', log=log)
        return proc.out == '1'

    async def apk_install(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        apk_id = request.match_info['apk_id']

        rows = await sql(request, """
                               SELECT project_id
                                 FROM avms
                                WHERE avm_id = %s
                               """, [avm.avm_id])

        project_id = rows[0][0]

        # check existence and permissions
        apk = await APK.get(request,
                            apk_id=apk_id,
                            project_id=project_id,
                            userid=userid)
        if not apk:
            raise web.HTTPNotFound(text="APK '%s' not found" % apk_id)

        log = request['slog']
        log.debug('request: APK install', apk_id=apk_id)

        # XXX checking here is not enough, the vm could be unavailable when
        # the task is executed.
        if not await self._bootcomplete(avm, log=log):
            raise web.HTTPConflict(text='The VM cannot install packages now.')

        command_id = uuid.uuid1().hex

        await request.app.task_broker.publish('apk_install', {
            'userid': userid,
            'project_id': project_id,
            'avm_id': avm.avm_id,
            'command_id': command_id,
            'apk_id': apk_id,
        }, log=log)

        response_js = {
            'command_id': command_id
        }

        ts_request = datetime.datetime.now()

        await sql(request, """
            INSERT INTO avm_commands (
                avm_id, command_id, ts_request
            ) VALUES (%s, %s, %s)
            """, [avm.avm_id, command_id, ts_request])

        return web.json_response(response_js, status=HTTPStatus.ACCEPTED)

    async def apk_list(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        log = request['slog']
        log.debug('Package list requested')

        proc = await cmd_docker_exec('{.avm_id}_adb'.format(avm),
                                     'adb', 'shell',
                                     'pm', 'list', 'packages', '-3', '-e', log=log)

        packages = [
            line.split('package:')[1]
            for line in proc.out_lines
        ]

        return web.json_response({'packages': packages})

    async def monkey(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        js = await json_request(request)
        packages = js['packages']
        event_count = js['event_count']
        throttle = js.get('throttle')

        log = request['slog']
        log.debug('request: monkey',
                  packages=packages,
                  event_count=event_count,
                  throttle=throttle)

        command_id = uuid.uuid1().hex

        await request.app.task_broker.publish('avm_monkey', {
            'userid': userid,
            'avm_id': avm.avm_id,
            'command_id': command_id,
            'packages': packages,
            'event_count': event_count,
            'throttle': throttle,
        }, log=log)

        ts_request = datetime.datetime.now()

        await sql(request, """
            INSERT INTO avm_commands (
                avm_id, command_id, ts_request
            ) VALUES (%s, %s, %s)
            """, [avm.avm_id, command_id, ts_request])

        response_js = {
            'command_id': command_id
        }

        # This should actually reply with a Location header and yadda yadda
        # but what to use behind a reverse proxy?
        # see https://www.adayinthelifeof.nl/2011/06/02/asynchronous-operations-in-rest/

        return web.json_response(response_js, status=HTTPStatus.ACCEPTED)

    async def command_status(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        command_id = request.match_info['command_id']

        request['slog'].debug('request: command result',
                              command_id=command_id)

        rows = await sql(request, """
            SELECT status,
                   COALESCE(proc_returncode::TEXT, '') AS proc_returncode,
                   COALESCE(proc_stdout, '') AS proc_stdout,
                   COALESCE(proc_stderr, '') AS proc_stderr
              FROM avm_commands
             WHERE avm_id = %s
                   AND command_id = %s
             """, [avm.avm_id, command_id])

        response_js = {
            'results': [
                {
                    'status': row[0],
                    'returncode': row[1],
                    'stdout': row[2],
                    'stderr': row[3],
                } for row in rows
            ]
        }

        return web.json_response(response_js)

    async def test_run(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        js = await json_request(request)
        package = js['package']

        log = request['slog']
        log.debug('request: test run')

        command_id = uuid.uuid1().hex

        await request.app.task_broker.publish('avm_test_run', {
            'userid': userid,
            'avm_id': avm.avm_id,
            'package': package,
            'command_id': command_id,
        }, log=log)

        ts_request = datetime.datetime.now()

        await sql(request, """
            INSERT INTO avm_commands (
                avm_id, command_id, ts_request
            ) VALUES (%s, %s, %s)
            """, [avm.avm_id, command_id, ts_request])

        response_js = {
            'command_id': command_id
        }

        # This should actually reply with a Location header and yadda yadda
        # but what to use behind a reverse proxy?
        # see https://www.adayinthelifeof.nl/2011/06/02/asynchronous-operations-in-rest/

        return web.json_response(response_js, status=HTTPStatus.ACCEPTED)

    _re_parse_instrumentation = re.compile('instrumentation:(?P<package>.*) \(target=(?P<target>.*)\)')

    async def test_list(self, request):
        userid = await authenticated_userid(request)
        avm = await request.app.context_avm(request, userid)

        log = request['slog']
        log.debug('Test package list requested')

        proc = await cmd_docker_exec('{.avm_id}_adb'.format(avm),
                                     'adb', 'shell', 'pm', 'list', 'instrumentation', log=log)

        packages = {}
        for line in proc.out_lines:
            m = self._re_parse_instrumentation.match(line)
            if not m:
                raise Exception('Cannot parse instrumentation package: %s' % line)
            packages[m.group('package')] = m.group('target')

        return web.json_response({'packages': packages})

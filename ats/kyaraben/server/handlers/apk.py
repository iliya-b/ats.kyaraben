
from http import HTTPStatus
import re
import uuid

from aiohttp import web

from ats.util.helpers import authenticated_userid
from ats.kyaraben.process import aiorun, ProcessError

from ats.kyaraben.model.apk import APK
from ats.kyaraben.server.handlers.misc import dump_stream


class APKHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('POST', '/projects/{project_id}/apk', self.upload)
        router.add_route('DELETE', '/projects/{project_id}/apk/{apk_id}', self.delete)
        router.add_route('GET', '/projects/{project_id}/apk', self.list)
        router.add_route('GET', '/projects/{project_id}/apk/{apk_id}', self.show)

    _re_parse_badging_package = re.compile("^package:.* name='(?P<package>.*?)'")

    async def upload(self, request):
        """
        Upload an apk to a project's docker volume
        """

        payload = await request.post()

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        filename = payload['file'].filename
        upload_stream = payload['file'].file

        apk_id = uuid.uuid1().hex

        log = request['slog']
        log.debug('request: apk upload', filename=filename)

        config = request.app.config

        tmppath = dump_stream(config['media']['tempdir'], upload_stream)

        try:
            ret = await aiorun('aapt', 'dump', 'badging', tmppath, log=log)
        except ProcessError:
            return web.HTTPBadRequest(text='File is not a valid apk')

        package = None

        for line in ret.out_lines:
            m = self._re_parse_badging_package.match(line)
            if m:
                package = m.group('package')

        log.debug('file dump', apk_id=apk_id, tmppath=tmppath)

        await APK.insert(request,
                         apk_id=apk_id,
                         filename=filename,
                         project_id=project.project_id,
                         package=package)

        await request.app.task_broker.publish('apk_upload', {
            'userid': userid,
            'project_id': project.project_id,
            'apk_id': apk_id,
            'tmppath': tmppath,
            'filename': filename
        }, log=log)

        response_js = {
            'apk_id': apk_id
        }

        return web.json_response(response_js, status=HTTPStatus.CREATED)

    async def delete(self, request):
        """
        Remove an apk from a project's docker volume
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        await request.post()

        apk_id = request.match_info['apk_id']

        log = request['slog']
        log.debug('request: apk delete', apk_id=apk_id)

        apk = await APK.get(request,
                            apk_id=apk_id,
                            project_id=project.project_id,
                            userid=userid)
        if not apk:
            raise web.HTTPNotFound(text="APK '%s' not found" % apk_id)

        await request.app.task_broker.publish('apk_delete', {
            'userid': userid,
            'project_id': project.project_id,
            'apk_id': apk_id,
        }, log=log)

        await apk.set_status(request, 'DELETING')

        return web.HTTPNoContent()

    async def list(self, request):
        """
        List the apks in a project
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        request['slog'].debug('APK list requested')

        response_js = {
            'apks': await APK.list(request, userid=userid, project_id=project.project_id)
        }

        return web.json_response(response_js)

    async def show(self, request):
        """
        Details of a single apk
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        apk_id = request.match_info['apk_id']

        apk = await APK.get(request,
                            apk_id=apk_id,
                            project_id=project.project_id,
                            userid=userid)
        if not apk:
            raise web.HTTPNotFound(text="APK '%s' not found" % apk_id)

        request['slog'].debug('APK list requested')

        response_js = {
            'apk': await apk.select(request)
        }

        return web.json_response(response_js)

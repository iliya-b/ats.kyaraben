# vim: set ai ts=8 sts=4 sw=4 et:

from http import HTTPStatus
import os
import uuid

from aiohttp import web

from ats.util.helpers import authenticated_userid
from ats.kyaraben.model.testsource import Testsource
from ats.kyaraben.model.apk import APK


class TestsourceHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/projects/{project_id}/testsources', self.list)
        router.add_route('GET', '/projects/{project_id}/testsources/{testsource_id}', self.download)
        router.add_route('GET', '/projects/{project_id}/testsources/{testsource_id}/metadata', self.metadata)
        router.add_route('POST', '/projects/{project_id}/testsources', self.upload)
        router.add_route('PUT', '/projects/{project_id}/testsources/{testsource_id}', self.update)
        router.add_route('DELETE', '/projects/{project_id}/testsources/{testsource_id}', self.delete)
        router.add_route('POST', '/projects/{project_id}/testsources/{testsource_id}/apk', self.compile)

    async def upload(self, request):
        """
        Upload a testsource file
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        payload = await request.post()

        try:
            filename = payload['file'].filename
        except KeyError:
            raise web.HTTPBadRequest(text='missing form field "file"')

        upload_stream = payload['file'].file

        try:
            content = upload_stream.read().decode('utf8')
        except UnicodeDecodeError:
            raise web.HTTPBadRequest(text='not utf8 or binary file')

        testsource_id = uuid.uuid1().hex

        request['slog'].debug('request: testsource upload', filename=filename)

        await Testsource.insert(request,
                                testsource_id=testsource_id,
                                filename=filename,
                                content=content,
                                project_id=project.project_id)

        response_js = {
            'testsource_id': testsource_id
        }

        testsource = await Testsource.get(request,
                                          testsource_id=testsource_id,
                                          project_id=project.project_id,
                                          userid=userid)

        await testsource.set_status(request, 'READY')

        return web.json_response(response_js, status=HTTPStatus.CREATED)

    async def update(self, request):
        """
        Upload a testsource file
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        testsource_id = request.match_info['testsource_id']

        testsource = await Testsource.get(request,
                                          testsource_id=testsource_id,
                                          project_id=project.project_id,
                                          userid=userid)

        payload = await request.post()

        try:
            filename = payload['file'].filename
        except KeyError:
            raise web.HTTPBadRequest(text='missing form field "file"')

        upload_stream = payload['file'].file

        try:
            content = upload_stream.read().decode('utf8')
        except UnicodeDecodeError:
            raise web.HTTPBadRequest(text='not utf8 or binary file')

        request['slog'].debug('request: testsource update', filename=filename)

        await testsource.update(request,
                                filename=filename,
                                content=content)

        await testsource.set_status(request, 'READY')

        return web.HTTPNoContent()

    async def delete(self, request):
        """
        Remove a testsource file and (if any) the associated apk
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        await request.post()

        testsource_id = request.match_info['testsource_id']

        log = request['slog']
        log.debug('request: testsource delete', testsource_id=testsource_id)

        testsource = await Testsource.get(request,
                                          testsource_id=testsource_id,
                                          project_id=project.project_id,
                                          userid=userid)
        if not testsource:
            raise web.HTTPNotFound(text="Testsource '%s' not found" % testsource_id)

        apk_id = await testsource.apk_id(request)

        if apk_id:
            apk = await APK.get(request,
                                apk_id=apk_id,
                                project_id=project.project_id,
                                userid=userid)
            if apk:
                await apk.set_status(request, 'DELETING')
                await request.app.task_broker.publish('apk_delete', {
                    'userid': userid,
                    'project_id': project.project_id,
                    'apk_id': apk_id,
                }, log=log)

        await testsource.delete(request)

        return web.HTTPNoContent()

    async def list(self, request):
        """
        List the testsources files in a project
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        request['slog'].debug('Testsource list requested')

        response_js = {
            'testsources': await Testsource.list(request, userid=userid, project_id=project.project_id)
        }

        return web.json_response(response_js)

    async def download(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        testsource_id = request.match_info['testsource_id']

        testsource = await Testsource.get(request,
                                          userid=userid,
                                          project_id=project.project_id,
                                          testsource_id=testsource_id)

        if not testsource:
            raise web.HTTPNotFound(text="Testsource '%s' not found" % testsource_id)

        content = await testsource.content(request)

        return web.Response(text=content)

    async def metadata(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        testsource_id = request.match_info['testsource_id']

        testsource = await Testsource.get(request,
                                          userid=userid,
                                          project_id=project.project_id,
                                          testsource_id=testsource_id)

        if not testsource:
            raise web.HTTPNotFound(text="Testsource '%s' not found" % testsource_id)

        metadata = await testsource.metadata(request)

        response_js = {
            'testsource': {
                'apk_id': metadata['apk_id'],
                'filename': metadata['filename'],
                'project_id': metadata['project_id'],
                'status': metadata['status'],
                'apk_status': metadata['apk_status'],
                'apk_status_reason': metadata['apk_status_reason'],
                'testsource_id': metadata['testsource_id'],
            }
        }

        return web.json_response(response_js)

    async def compile(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        testsource_id = request.match_info['testsource_id']

        testsource = await Testsource.get(request,
                                          userid=userid,
                                          project_id=project.project_id,
                                          testsource_id=testsource_id)

        if not testsource:
            raise web.HTTPNotFound(text="Testsource '%s' not found" % testsource_id)

        apk_id = await testsource.apk_id(request)
        filename = await testsource.filename(request)

        if not apk_id:
            apk_id = uuid.uuid1().hex

        basename, extension = os.path.splitext(filename)

        await testsource.update_apk(request, apk_id=None)

        await APK.insert(request,
                         apk_id=apk_id,
                         filename='{}.apk'.format(basename),
                         project_id=project.project_id)

        await testsource.update_apk(request, apk_id=apk_id)

        apk = await APK.get(request,
                            apk_id=apk_id,
                            project_id=project.project_id,
                            userid=userid)

        await apk.set_status(request, 'QUEUED')

        await testsource.update_apk(request,
                                    apk_id=apk_id)

        await request.app.task_broker.publish('testsource_compile', {
            'userid': userid,
            'project_id': project.project_id,
            'testsource_id': testsource_id,
        }, log=request['slog'])

        response_js = {
            'apk_id': apk_id
        }

        return web.json_response(response_js, status=HTTPStatus.ACCEPTED)

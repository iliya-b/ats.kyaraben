
from http import HTTPStatus
import os
import re
import uuid

from aiohttp import web

from ats.util.helpers import authenticated_userid
from ats.kyaraben.model.camera import Camera
from ats.kyaraben.server.handlers.misc import dump_stream


re_filename_ext = re.compile('^\.[a-zA-Z0-9_-]+$')


class CameraFileHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('POST', '/projects/{project_id}/camera', self.upload)
        router.add_route('DELETE', '/projects/{project_id}/camera/{camera_file_id}', self.delete)
        router.add_route('GET', '/projects/{project_id}/camera', self.list)

    async def upload(self, request):
        """
        Upload a camera file to a project's docker volume
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        payload = await request.post()

        filename = payload['file'].filename
        upload_stream = payload['file'].file

        ext = os.path.splitext(filename)[1]

        if not re_filename_ext.match(ext):
            # paranoid check in case a script doesn't protect from code injection
            raise web.HTTPBadRequest(text='file extension not supported: %s' % filename)

        camera_id = uuid.uuid1().hex

        log = request['slog']
        log.debug('request: camera upload', filename=filename)

        config = request.app.config

        tmppath = dump_stream(config['media']['tempdir'], upload_stream)

        log.debug('file dump', camera_id=camera_id, tmppath=tmppath)

        await Camera.insert(request,
                            camera_id=camera_id,
                            filename=filename,
                            project_id=project.project_id)

        await request.app.task_broker.publish('camera_upload', {
            'userid': userid,
            'project_id': project.project_id,
            'camera_id': camera_id,
            'tmppath': tmppath,
            'filename': filename
        }, log=log)

        response_js = {
            'camera_file_id': camera_id
        }

        return web.json_response(response_js, status=HTTPStatus.CREATED)

    async def delete(self, request):
        """
        Remove a camera file from a project's docker volume
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        await request.post()

        camera_id = request.match_info['camera_file_id']

        log = request['slog']
        log.debug('request: camera delete', camera_id=camera_id)

        camera = await Camera.get(request,
                                  camera_id=camera_id,
                                  project_id=project.project_id,
                                  userid=userid)
        if not camera:
            raise web.HTTPNotFound(text="Camera file '%s' not found" % camera_id)

        await request.app.task_broker.publish('camera_delete', {
            'userid': userid,
            'project_id': project.project_id,
            'camera_id': camera_id,
        }, log=log)

        await camera.set_status(request, 'DELETING')

        return web.HTTPNoContent()

    async def list(self, request):
        """
        List the camera files in a project
        """

        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        request['slog'].debug('Camera list requested')

        response_js = {
            'camera_files': await Camera.list(request, userid=userid, project_id=project.project_id)
        }

        return web.json_response(response_js)

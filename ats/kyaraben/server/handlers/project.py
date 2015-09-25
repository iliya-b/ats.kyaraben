
from http import HTTPStatus
import uuid

from aiohttp import web

from ats.util.helpers import authenticated_userid, json_request
from ats.kyaraben.model.project import Project


class ProjectHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/projects', self.list)
        router.add_route('GET', '/projects/{project_id}', self.show)
        router.add_route('POST', '/projects', self.create)
        router.add_route('PUT', '/projects/{project_id}', self.update)
        router.add_route('DELETE', '/projects/{project_id}', self.delete)

    async def list(self, request):
        """
        List projects available to the user
        """
        userid = await authenticated_userid(request)

        request['slog'].debug('request: project list')

        response_js = {
            'projects': await Project.list(request, userid=userid)
        }

        return web.json_response(response_js)

    async def show(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        response_js = {
            'project': await project.select(request)
        }

        return web.json_response(response_js)

    async def create(self, request):
        """
        Create a new project
        """
        userid = await authenticated_userid(request)
        project_id = uuid.uuid1().hex

        js = await json_request(request)

        log = request['slog']
        log.debug('request: project create', body=js)

        try:
            project_name = js['project_name']
        except KeyError:
            raise web.HTTPBadRequest(text='project_name is required')

        await Project.insert(request,
                             project_id=project_id,
                             project_name=project_name,
                             userid=userid)

        await request.app.task_broker.publish('project_container_create', {
            'userid': userid,
            'project_id': project_id,
        }, log=log)

        response_js = {
            'project_id': project_id
        }

        return web.json_response(response_js, status=HTTPStatus.CREATED)

    async def update(self, request):
        """
        Update a project's data
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        js = await json_request(request)

        try:
            project_name = js['project_name']
        except KeyError:
            raise web.HTTPBadRequest(text='project_name is required')

        request['slog'].debug('request: project update', body=js)
        await project.update(request, project_name=project_name)

        return web.HTTPNoContent()

    async def delete(self, request):
        """
        Delete an existing project
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        log = request['slog']
        log.debug('request: project delete')

        if await project.is_active(request):
            raise web.HTTPConflict(text='cannot delete project with active vms or campaigns')

        await request.app.task_broker.publish('project_container_delete', {
            'userid': userid,
            'project_id': project.project_id,
        }, log=log)

        await project.set_status(request, status='DELETING')

        return web.HTTPAccepted()

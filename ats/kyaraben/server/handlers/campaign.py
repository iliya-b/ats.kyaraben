
from http import HTTPStatus
import uuid

from aiohttp import web

from ats.util.helpers import authenticated_userid, json_request
from ats.kyaraben.model.apk import APK
from ats.kyaraben.model.campaign import Campaign

import petname


class CampaignHandler:
    def setup_routes(self, app):
        router = app.router
        router.add_route('GET', '/projects/{project_id}/campaigns/{campaign_id}', self.show)
        router.add_route('GET', '/projects/{project_id}/campaigns', self.list)
        router.add_route('POST', '/projects/{project_id}/campaigns', self.run)
        router.add_route('DELETE', '/projects/{project_id}/campaigns/{campaign_id}', self.delete)

    async def list(self, request):
        """
        List the campaigns in a project
        """
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        request['slog'].debug('Campaign list requested')

        response_js = {
            'campaigns': await Campaign.list(request, userid=userid, project_id=project.project_id)
        }

        return web.json_response(response_js)

    async def run(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        log = request['slog']
        log.debug('request: project campaign')

        # could add a jsonschema here..
        js = await json_request(request)

        tests = js['tests']

        campaign_id = uuid.uuid1().hex
        campaign_name = js.get('campaign_name', petname.Generate(3, '-'))

        if len(campaign_name) > 50:
            raise web.HTTPBadRequest(text='campaign_name too long (max 50)')

        for test in tests:
            # XXX can check test['images']
            # XXX but no easy way to check packages.
            for apk_id in test['apks']:
                # check permission etc.
                apk = await APK.get(request,
                                    apk_id=apk_id,
                                    project_id=project.project_id,
                                    userid=userid)
                if not apk:
                    raise web.HTTPNotFound(text="APK '%s' not found" % apk_id)

        await Campaign.insert(request,
                              campaign_id=campaign_id,
                              campaign_name=campaign_name,
                              project_id=project.project_id,
                              tests=tests)

        await request.app.task_broker.publish('campaign_run', {
            'campaign_id': campaign_id,
            'userid': userid,
            'project_id': project.project_id,
        }, log=log)

        response_js = {
            'campaign_id': campaign_id
        }

        return web.json_response(response_js, status=HTTPStatus.ACCEPTED)

    async def show(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        campaign_id = request.match_info['campaign_id']

        campaign = await Campaign.get(request,
                                      userid=userid,
                                      project_id=project.project_id,
                                      campaign_id=campaign_id)

        if not campaign:
            raise web.HTTPNotFound(text="Campaign '%s' not found" % campaign_id)

        response_js = {
            'campaign': await campaign.results(request)
        }

        return web.json_response(response_js)

    async def delete(self, request):
        userid = await authenticated_userid(request)
        project = await request.app.context_project(request, userid)

        await request.post()

        campaign_id = request.match_info['campaign_id']

        log = request['slog']
        log.debug('request: campaign delete', campaign_id=campaign_id)

        campaign = await Campaign.get(request,
                                      campaign_id=campaign_id,
                                      project_id=project.project_id,
                                      userid=userid)
        if not campaign:
            raise web.HTTPNotFound(text="Campaign '%s' not found" % campaign_id)

        await request.app.task_broker.publish('campaign_delete', {
            'userid': userid,
            'project_id': project.project_id,
            'campaign_id': campaign_id,
        }, log=log)

        await campaign.set_status(request, 'DELETING')

        return web.HTTPNoContent()


import aiopg
from aiohttp import web

from ats.kyaraben.model.android import AndroidVM
from ats.kyaraben.model.project import Project
from ats.kyaraben.tasks import TaskBroker, ConnectionFactory

from .handlers.gateway import GatewayHandler
from .handlers.android import AndroidHandler
from .handlers.apk import APKHandler
from .handlers.camera import CameraFileHandler
from .handlers.campaign import CampaignHandler
from .handlers.image import ImageHandler
from .handlers.project import ProjectHandler
from .handlers.testsource import TestsourceHandler
from .handlers.user import UserHandler


class KyarabenApp(web.Application):
    def __init__(self, config, *args, **kw):
        super().__init__(*args, **kw)
        self.config = config
        self.dbpool = None
        self.task_broker = None

    async def setup(self):
        await self.setup_db()
        await self.setup_amqp()
        self.setup_routes()
        self.logger.debug('setup done.')

    def setup_routes(self):
        GatewayHandler().setup_routes(app=self)
        AndroidHandler().setup_routes(app=self)
        APKHandler().setup_routes(app=self)
        CameraFileHandler().setup_routes(app=self)
        CampaignHandler().setup_routes(app=self)
        ImageHandler().setup_routes(app=self)
        ProjectHandler().setup_routes(app=self)
        TestsourceHandler().setup_routes(app=self)
        UserHandler().setup_routes(app=self)

    async def setup_amqp(self):
        self.logger.debug('Set up AMQP..')
        connection_factory = ConnectionFactory(host=self.config['amqp']['hostname'],
                                               login=self.config['amqp']['admin_username'],
                                               password=self.config['amqp']['admin_password'])
        self.task_broker = TaskBroker(connection_factory=connection_factory)
        await self.task_broker.setup()

    async def setup_db(self):
        self.logger.debug('Set up DBMS connection pool...')
        self.dbpool = await aiopg.create_pool(self.config['db']['dsn'])

    async def context_avm(self, request, userid):
        avm_id = request.match_info['avm_id']

        request['slog'] = request['slog'].bind(avm=avm_id)

        avm = await AndroidVM.get(self, userid=userid, avm_id=avm_id)
        if not avm:
            raise web.HTTPNotFound(text="AVM '%s' not found" % avm_id)
        return avm

    async def context_project(self, request, userid, project_id=None):
        if project_id is None:
            project_id = request.match_info['project_id']

        request['slog'] = request['slog'].bind(project=project_id)

        project = await Project.get(self, userid=userid, project_id=project_id)
        if not project:
            raise web.HTTPNotFound(text="Project '%s' not found" % project_id)
        return project

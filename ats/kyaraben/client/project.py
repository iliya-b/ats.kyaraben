
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne


class Create(Command):
    "Create a new project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_name',
                        help='user-defined name of the project '
                             '(needs not be unique)')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting project creation...')

        payload = {
            'project_name': parsed_args.project_name
        }

        r = self.app.do_post('projects',
                             headers=self.app.auth_header(parsed_args),
                             json=payload)

        js = r.json()
        project_id = js['project_id']

        self.app.LOG.debug('Project creation started: %s', project_id)

        print(js['project_id'])


class Update(Command):
    "Update an existing project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('--project-name',
                        help='name of the project '
                             '(needs not be unique)')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting project update...')

        payload = {
            'project_name': parsed_args.project_name
        }

        project_id = parsed_args.project_id

        self.app.do_put('projects', project_id,
                        headers=self.app.auth_header(parsed_args),
                        json=payload)


class List(Lister):
    "List all available projects"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting project list...')

        r = self.app.do_get('projects',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        projects = js['projects']

        if not projects:
            self.app.LOG.info('No project found')

        return self.app.list2fields(projects)


class Show(ShowOne):
    "Retrieve information about a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Showing project')
        project_id = parsed_args.project_id

        r = self.app.do_get('projects', project_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        project = js['project']

        return self.dict2columns(project)


class Delete(Command):
    "Delete a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id', nargs='+')
        return ap

    def take_action(self, parsed_args):
        for project_id in parsed_args.project_id:
            self.app.do_delete('projects', project_id,
                               headers=self.app.auth_header(parsed_args))
            self.app.LOG.info('Deleted %s', project_id)

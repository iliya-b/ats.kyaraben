
import argparse
from pathlib import Path

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne


class Upload(Command):
    "Add a testsource to a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('file',
                        type=argparse.FileType('rb'),
                        help='testsource file to upload')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting testsource upload...')
        project_id = parsed_args.project_id

        filep = Path(parsed_args.file.name).absolute()
        filename = filep.parts[-1]

        self.app.LOG.debug('project_id: %s', project_id)
        self.app.LOG.debug('file: %s', filep)

        files = {
            'file': filep.open('rb')
        }

        r = self.app.do_post('projects', project_id, 'testsources',
                             headers=self.app.auth_header(parsed_args),
                             files=files)

        js = r.json()
        self.app.LOG.debug('Uploading %s', filename)
        print(js['testsource_id'])


class Update(Command):
    "Update a testsource, possibly renaming it"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('testsource_id')
        ap.add_argument('file',
                        type=argparse.FileType('rb'),
                        help='testsource file to upload')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting testsource upload...')
        project_id = parsed_args.project_id
        testsource_id = parsed_args.testsource_id

        filep = Path(parsed_args.file.name).absolute()
        filename = filep.parts[-1]

        self.app.LOG.debug('project_id: %s', project_id)
        self.app.LOG.debug('testsource_id: %s', testsource_id)
        self.app.LOG.debug('file: %s', filep)

        files = {
            'file': filep.open('rb')
        }

        self.app.do_put('projects', project_id, 'testsources', testsource_id,
                        headers=self.app.auth_header(parsed_args),
                        files=files)

        self.app.LOG.info('Updating %s', filename)


class Download(Command):
    "Download a testsource"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('testsource_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Dowloading testsource')
        project_id = parsed_args.project_id
        testsource_id = parsed_args.testsource_id

        r = self.app.do_get('projects', project_id, 'testsources', testsource_id,
                            headers=self.app.auth_header(parsed_args))

        content = r.text
        print(content)


class Delete(Command):
    "Delete a testsource from a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('testsource',
                        nargs='+',
                        help='testsource file(s) to delete')
        return ap

    def take_action(self, parsed_args):
        project_id = parsed_args.project_id

        for testsource in parsed_args.testsource:
            self.app.LOG.debug('Requesting testsource delete...')
            self.app.LOG.debug('project: %s - testsource: %s', project_id, testsource)

            self.app.do_delete('projects', project_id, 'testsources', testsource,
                               headers=self.app.auth_header(parsed_args))

            self.app.LOG.info('Deleted %s', testsource)


class List(Lister):
    "List testsources in a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting testsource list...')
        project_id = parsed_args.project_id

        self.app.LOG.debug('project_id: %s', project_id)

        r = self.app.do_get('projects', project_id, 'testsources',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        testsources = js['testsources']

        if not testsources:
            self.app.LOG.info('No testsource file found')

        return self.app.list2fields(testsources)


class Show(ShowOne):
    "Retrieve information about a test source"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('testsource_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Showing testsource')
        project_id = parsed_args.project_id
        testsource_id = parsed_args.testsource_id

        r = self.app.do_get('projects', project_id, 'testsources', testsource_id, 'metadata',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        testsource = js['testsource']

        return self.dict2columns(testsource)


class Compile(Command):
    "Compile a testsource"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('testsource_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting testsource compilation...')
        project_id = parsed_args.project_id
        testsource_id = parsed_args.testsource_id

        self.app.LOG.debug('project_id: %s', project_id)
        self.app.LOG.debug('testsource_id: %s', testsource_id)

        r = self.app.do_post('projects', project_id, 'testsources', testsource_id, 'apk',
                             headers=self.app.auth_header(parsed_args))

        js = r.json()
        apk_id = js['apk_id']

        self.app.LOG.info('Compiling APK %s', apk_id)
        print(apk_id)

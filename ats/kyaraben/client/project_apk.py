
import argparse
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne
from pathlib import Path


class Upload(Command):
    "Add an APK to a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('file',
                        type=argparse.FileType('rb'),
                        help='apk file to upload')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting apk upload...')
        project_id = parsed_args.project_id

        filep = Path(parsed_args.file.name).absolute()
        apk_name = filep.parts[-1]

        self.app.LOG.debug('project_id: %s', project_id)
        self.app.LOG.debug('file: %s', filep)

        files = {
            'file': filep.open('rb')
        }

        r = self.app.do_post('projects', project_id, 'apk',
                             headers=self.app.auth_header(parsed_args),
                             files=files)

        js = r.json()

        self.app.LOG.debug('Uploading %s', apk_name)
        print(js['apk_id'])


class Delete(Command):
    "Delete an APK from a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('apk_id',
                        nargs='+',
                        help='apk(s) to delete')
        return ap

    def take_action(self, parsed_args):
        project_id = parsed_args.project_id

        for apk_id in parsed_args.apk_id:
            self.app.LOG.debug('Requesting apk delete...')
            self.app.LOG.debug('project: %s - apk_id: %s', project_id, apk_id)

            self.app.do_delete('projects', project_id, 'apk', apk_id,
                               headers=self.app.auth_header(parsed_args))

            self.app.LOG.info('Deleted %s', apk_id)


class List(Lister):
    "List the APKs in a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting apk list...')

        project_id = parsed_args.project_id

        r = self.app.do_get('projects', project_id, 'apk',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        apks = js['apks']

        if not apks:
            self.app.LOG.info('No APK found')

        return self.app.list2fields(apks)


class Show(ShowOne):
    "Retrieve APK details"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('apk_id')
        return ap

    def take_action(self, parsed_args):
        project_id = parsed_args.project_id
        apk_id = parsed_args.apk_id

        r = self.app.do_get('projects', project_id, 'apk', apk_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        apk = js['apk']

        return self.dict2columns(apk)


import argparse
from cliff.command import Command
from cliff.lister import Lister
from pathlib import Path


class Upload(Command):
    "Add a camera_file to a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('file',
                        type=argparse.FileType('rb'),
                        help='camera_file file to upload')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting camera_file upload...')
        project_id = parsed_args.project_id

        filep = Path(parsed_args.file.name).absolute()
        filename = filep.parts[-1]

        self.app.LOG.debug('project_id: %s', project_id)
        self.app.LOG.debug('file: %s', filep)

        files = {
            'file': filep.open('rb')
        }

        r = self.app.do_post('projects', project_id, 'camera',
                             headers=self.app.auth_header(parsed_args),
                             files=files)

        js = r.json()

        self.app.LOG.debug('Uploading %s', filename)
        print(js['camera_file_id'])


class Delete(Command):
    "Delete a camera_file from a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('camera_file',
                        nargs='+',
                        help='camera file(s) to delete')
        return ap

    def take_action(self, parsed_args):
        project_id = parsed_args.project_id

        for camera_file in parsed_args.camera_file:
            self.app.LOG.debug('Requesting camera_file delete...')
            self.app.LOG.debug('project: %s - camera_file: %s', project_id, camera_file)

            self.app.do_delete('projects', project_id, 'camera', camera_file,
                               headers=self.app.auth_header(parsed_args))

            self.app.LOG.info('Deleted %s', camera_file)


class List(Lister):
    "List the camera_files in a project"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting camera_file list...')

        project_id = parsed_args.project_id

        r = self.app.do_get('projects', project_id, 'camera',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        camera_files = js['camera_files']

        if not camera_files:
            self.app.LOG.info('No camera file found')

        return self.app.list2fields(camera_files)

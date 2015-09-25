
import argparse
import json

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne


class Run(Command):
    "Run a test campaign"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('--campaign-name',
                        help='name of the campaign '
                             '(needs not be unique)')
        ap.add_argument('--file',
                        type=argparse.FileType('r'),
                        help='JSON file of the form '
                        '{"tests": [{'
                        '"image": "image_name", '
                        '"apks": [apk_id, ...], '
                        '"packages": [package_name, ...]'
                        '}, ...]}')
        ap.add_argument('--image',
                        nargs='+', action='append',
                        help='android images to deploy')
        ap.add_argument('--apk',
                        nargs='+', action='append',
                        help='apk files to install')
        ap.add_argument('--package',
                        nargs='+', action='append',
                        help='test packages to run')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting test campaign...')

        filep = parsed_args.file
        project_id = parsed_args.project_id

        # hack to accept both "--apk apk1 apk2" and "--apk apk1 --apk apk2"

        if parsed_args.file and (parsed_args.image or parsed_args.apk or parsed_args.package):
            raise Exception('The --file option cannot be used with --image, --apk and --package')

        if filep:
            payload = json.load(filep)
        else:
            images = sum(parsed_args.image or [], [])
            if not images:
                raise Exception('The --image parameter is required, if not using --file')

            apks = sum(parsed_args.apk or [], [])
            if not apks:
                raise Exception('The --apk parameter is required, if not using --file')

            packages = sum(parsed_args.package or [], [])
            if not packages:
                raise Exception('The --package parameter is required, if not using --file')

            payload = {
                'tests': [
                    {
                        'image': image,
                        'apks': apks,
                        'packages': packages
                    } for image in images
                ]
            }

        if parsed_args.campaign_name is not None:
            payload['campaign_name'] = parsed_args.campaign_name

        r = self.app.do_post('projects', project_id, 'campaigns',
                             headers=self.app.auth_header(parsed_args),
                             json=payload)

        js = r.json()
        campaign_id = js['campaign_id']

        self.app.LOG.info('Test campaign requested: %s.', payload)

        print(campaign_id)


class List(Lister):
    "List all campaigns"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)

        ap.add_argument('project_id')

        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting campaign list...')
        project_id = parsed_args.project_id

        r = self.app.do_get('projects', project_id, 'campaigns',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()

        campaigns = js['campaigns']

        if not campaigns:
            self.app.LOG.info('No campaign found')

        return self.app.list2fields(campaigns)


class Show(ShowOne):
    "Retrieve information about a test campaign"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('campaign_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Showing campaign')
        project_id = parsed_args.project_id
        campaign_id = parsed_args.campaign_id

        r = self.app.do_get('projects', project_id, 'campaigns', campaign_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        campaign = js['campaign']

        return self.dict2columns(campaign)


class Delete(Command):
    "Delete test campaign(s)"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')
        ap.add_argument('campaign_id',
                        nargs='+',
                        help='campaigns to delete')
        return ap

    def take_action(self, parsed_args):
        project_id = parsed_args.project_id

        for campaign_id in parsed_args.campaign_id:
            self.app.LOG.debug('Requesting campaign delete...')
            self.app.LOG.debug('project: %s - campaign_id: %s', project_id, campaign_id)

            self.app.do_delete('projects', project_id, 'campaigns', campaign_id,
                               headers=self.app.auth_header(parsed_args))

            self.app.LOG.info('Deleted %s', campaign_id)

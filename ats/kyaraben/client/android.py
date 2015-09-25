
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne


class Create(Command):
    "Create and register an Android VM stack, including services"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('project_id')

        ap.add_argument('--image',
                        required=True,
                        help='ROM image to use. e.g. '
                             '--image=foo for system-foo and data-foo.',
                        default='')

        ap.add_argument('--avm-name',
                        help='assigned name of the AVM')

        ap.add_argument('--width',
                        type=int,
                        help='screen width')

        ap.add_argument('--height',
                        type=int,
                        help='screen height')

        ap.add_argument('--dpi',
                        type=int,
                        help='screen dpi')

        for stuff in [
                'sensors', 'battery', 'gps', 'camera',
                'record', 'gsm', 'nfc']:
            group = ap.add_mutually_exclusive_group()
            group.add_argument('--enable-%s' % stuff,
                               dest='enable_%s' % stuff,
                               action='store_const',
                               const=1)
            group.add_argument('--disable-%s' % stuff,
                               dest='enable_%s' % stuff,
                               action='store_const',
                               const=0)

        ap.set_defaults(
            enable_sensors=None,
            enable_battery=None,
            enable_gps=None,
            enable_camera=None,
            enable_record=None,
            enable_gsm=None,
            enable_nfc=None,
        )

        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting Android VM creation...')

        hwconfig = {}

        options = [
            'width', 'height', 'dpi', 'enable_sensors', 'enable_battery', 'enable_gps',
            'enable_camera', 'enable_record', 'enable_gsm', 'enable_nfc'
        ]

        for option in options:
            value = getattr(parsed_args, option, None)
            if value is not None:
                hwconfig[option] = value

        payload = {
            'project_id': parsed_args.project_id,
            'image': parsed_args.image,
            'hwconfig': hwconfig
        }

        if parsed_args.avm_name is not None:
            payload['avm_name'] = parsed_args.avm_name

        r = self.app.do_post('android',
                             headers=self.app.auth_header(parsed_args),
                             json=payload)

        js = r.json()
        avm_id = js['avm_id']

        self.app.LOG.debug('Android VM creation started: %s' % avm_id)

        print(js['avm_id'])


class List(Lister):
    "List/search Android VMs"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)

        ap.add_argument('--project-id',
                        required=False,
                        help='id of the parent project.')

        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Searching Android VMs')

        params = {}
        if parsed_args.project_id:
            params['project_id'] = parsed_args.project_id

        r = self.app.do_get('android',
                            headers=self.app.auth_header(parsed_args), params=params)

        js = r.json()
        avms = js['avms']

        if not avms:
            self.app.LOG.info('No VM found')

        return self.app.list2fields(avms)


class Show(ShowOne):
    "Retrieve information about an Android VM stack"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Showing Android VM')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        avm = js['avm']

        return self.dict2columns(avm)


class Delete(Command):
    "Remove an Android VM stack, including services"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id', nargs='+')
        return ap

    def take_action(self, parsed_args):
        for avm_id in parsed_args.avm_id:
            self.app.do_delete('android', avm_id,
                               headers=self.app.auth_header(parsed_args))
            self.app.LOG.info('Deleted %s', avm_id)


class DisplayURL(Command):
    "URL to use for a NoVNC console"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving display URL')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        avm = js['avm']

        print('http://kanaka.github.io/noVNC/noVNC/vnc_auto.html'
              '?host={host}&port={port}'.format(
                  host=avm['novnc_host'],
                  port=avm['novnc_port']
              ))


class GetOTP(Command):
    "Get a one-time password (valid for 30s)"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving password')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id, 'totp',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        totp = js['totp']

        print(totp)


class Monkey(Command):
    "Run monkey"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        ap.add_argument('event_count', type=int)
        ap.add_argument('--package', action='append',
                        required=True,
                        help='Run monkey on this package')
        ap.add_argument('--throttle',
                        required=False, type=int,
                        help='Throttle the events sent to the VM')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Running monkey')
        avm_id = parsed_args.avm_id

        payload = {}
        payload['event_count'] = parsed_args.event_count
        payload['packages'] = parsed_args.package

        if parsed_args.throttle:
            payload['throttle'] = parsed_args.throttle

        r = self.app.do_post('android', avm_id, 'monkey',
                             headers=self.app.auth_header(parsed_args),
                             json=payload)

        js = r.json()
        command_id = js['command_id']

        self.app.LOG.info('To retrieve the result, run "kyaraben android command status %s %s"',
                          avm_id, command_id)

        print(command_id)


class CommandStatus(ShowOne):
    "Show command result"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        ap.add_argument('command_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving command results')
        avm_id = parsed_args.avm_id
        command_id = parsed_args.command_id

        r = self.app.do_get('android', avm_id, 'command', command_id,
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        result = js['results'][0]

        return self.dict2columns(result)


class TestRun(Command):
    "Run a test set"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        ap.add_argument('package')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting test run...')
        avm_id = parsed_args.avm_id

        payload = {
            'package': parsed_args.package
        }

        r = self.app.do_post('android', avm_id, 'testrun',
                             headers=self.app.auth_header(parsed_args),
                             json=payload)

        js = r.json()
        command_id = js['command_id']

        self.app.LOG.info('To retrieve the result, run "kyaraben android command status %s %s"',
                          avm_id, command_id)

        print(command_id)


class TestList(Lister):
    "List the test packages in a vm"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Listing test packages')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id, 'testrun',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        packages = js['packages']

        # inconsistent API
        packages = [
            {
                'package': key,
                'target': value
            } for key, value in packages.items()
        ]

        return self.app.list2fields(packages)


class Properties(ShowOne):
    "Read Android system properties"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Listing properties')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id, 'properties',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        properties = js['properties']

        return self.dict2columns(properties)


class Update(Command):
    "Update an existing VM"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        ap.add_argument('--avm-name',
                        help='name of the vm '
                             '(needs not be unique)')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting avm update...')

        payload = {
            'avm_name': parsed_args.avm_name
        }

        avm_id = parsed_args.avm_id

        self.app.do_put('android', avm_id,
                        headers=self.app.auth_header(parsed_args),
                        json=payload)

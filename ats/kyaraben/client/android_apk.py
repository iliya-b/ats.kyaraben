
from cliff.command import Command
from cliff.lister import Lister


class Install(Command):
    "Install an APK"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        ap.add_argument('apk_id',
                        help='apk file to install')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Requesting apk install...')

        avm_id = parsed_args.avm_id
        apk_id = parsed_args.apk_id

        r = self.app.do_post('android', avm_id, 'apk', apk_id,
                             headers=self.app.auth_header(parsed_args))

        js = r.json()
        command_id = js['command_id']

        self.app.LOG.info('Install requested: %s on %s.', apk_id, avm_id)

        self.app.LOG.info('To know if the installation is successful, run "kyaraben android command status %s %s"',
                          avm_id, command_id)

        print(js['command_id'])


class List(Lister):
    "List installed packages"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Listing packages')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('android', avm_id, 'apk',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()

        # inconsistent API
        packages = [{
            'package': package
        } for package in js['packages']]

        return self.app.list2fields(packages)

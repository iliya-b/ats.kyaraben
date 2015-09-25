
from cliff.show import ShowOne


class AndroidPorts(ShowOne):
    "Retrieve connection information for an Android VM"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        ap.add_argument('avm_id')
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving VM ports')
        avm_id = parsed_args.avm_id

        r = self.app.do_get('gateway', 'android', avm_id, 'ports')

        js = r.json()
        avm = js['avm']

        return self.dict2columns(avm)

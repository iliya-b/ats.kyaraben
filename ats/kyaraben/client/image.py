
from cliff.lister import Lister


class List(Lister):
    "List Android images"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Searching Android images')

        r = self.app.do_get('images')

        js = r.json()

        images = js['images']

        if not images:
            self.app.LOG.info('No image')

        return self.app.list2fields(images)

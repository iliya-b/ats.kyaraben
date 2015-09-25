
from cliff.show import ShowOne


class Quota(ShowOne):
    "Retrieve user quota parameters"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving quota parameters...')

        r = self.app.do_get('user', 'quota',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        quota = js['quota']

        return self.dict2columns(quota)


class Whoami(ShowOne):
    "Retrieve user parameters"

    def get_parser(self, prog_name):
        ap = super().get_parser(prog_name)
        self.app.add_auth_options(ap)
        return ap

    def take_action(self, parsed_args):
        self.app.LOG.debug('Retrieving user parameters...')

        r = self.app.do_get('user', 'whoami',
                            headers=self.app.auth_header(parsed_args))

        js = r.json()
        user = js['user']

        return self.dict2columns(user)

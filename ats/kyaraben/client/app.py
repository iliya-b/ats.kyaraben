
import sys
import warnings

from cliff.commandmanager import CommandManager

import ats.kyaraben
from ats.client.client import ClientApp

warnings.filterwarnings("ignore", category=DeprecationWarning)


class App(ClientApp):
    default_config_file = 'kyaraben-client.ini'

    def __init__(self):
        super().__init__(
            description='kyaraben',
            version=ats.kyaraben.version,
            command_manager=CommandManager('kyaraben'))


def main(argv=sys.argv[1:]):
    app = App()
    return app.run(argv)

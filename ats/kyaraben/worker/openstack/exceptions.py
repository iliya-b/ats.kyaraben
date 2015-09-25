
class OSHeatError(Exception):
    pass


class AVMNotFoundError(OSHeatError):
    pass


class AVMCreationError(OSHeatError):
    pass


class AVMImageNotFoundError(AVMCreationError):
    pass

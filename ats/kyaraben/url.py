
def urlpath(*parts):
    """
    There is no real equivalent in stdlib
    """
    return '/'.join(s.strip('/') for s in parts)

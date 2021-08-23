import datetime

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions


def print_now():
    return datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:%M:%S.%f")

import inspect
import os


def _get_trafficclient_version():
    """Read version from versioninfo file."""
    mod_abspath = inspect.getabsfile(inspect.currentframe())
    trafficclient_path = os.path.dirname(mod_abspath)
    version_path = os.path.join(trafficclient_path, 'versioninfo')

    if os.path.exists(version_path):
        version = open(version_path).read().strip()
    else:
        version = "Unknown, couldn't find versioninfo file at %s"\
                  % version_path

    return version


__version__ = _get_trafficclient_version()
    
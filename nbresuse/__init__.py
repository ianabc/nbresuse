import os
import json
import psutil
from traitlets import Float, Int, Unicode, default
from traitlets.config import Configurable
from notebook.utils import url_path_join
from notebook.base.handlers import IPythonHandler


class MetricsHandler(IPythonHandler):
    def get(self):
        """
        Calculate and return current resource usage metrics
        """
        config = self.settings['nbresuse_display_config']
        
        disk_statvfs = os.statvfs(os.environ.get('HOME', '/'))
        disk = {}
        disk['frsize'] = disk_statvfs.f_frsize
        disk['size']  = disk_statvfs.f_blocks
        disk['avail'] = disk_statvfs.f_bavail
        disk['used']  = disk['size'] - disk['avail']

        cur_process = psutil.Process()
        all_processes = [cur_process] + cur_process.children(recursive=True)
        rss = sum([p.memory_info().rss for p in all_processes])

        limits = {}

        if config.mem_limit != 0:
            limits['memory'] = {
                'rss': config.mem_limit
            }
            if config.mem_warning_threshold != 0:
                limits['memory']['warn'] = (config.mem_limit - rss) < (config.mem_limit * config.mem_warning_threshold)

        if config.disk_warning_threshold != 0:
            limits['disk'] = {}
            limits['disk']['warn'] = disk['avail'] < (disk['size'] * config.disk_warning_threshold)

        metrics = {
            'rss': rss,
            'disk': disk,
            'limits': limits
        }
        self.write(json.dumps(metrics))


def _jupyter_server_extension_paths():
    """
    Set up the server extension for collecting metrics
    """
    return [{
        'module': 'nbresuse',
    }]

def _jupyter_nbextension_paths():
    """
    Set up the notebook extension for displaying metrics
    """
    return [{
        "section": "notebook",
        "dest": "nbresuse",
        "src": "static",
        "require": "nbresuse/main"
    }]

class ResourceUseDisplay(Configurable):
    """
    Holds server-side configuration for nbresuse
    """

    mem_warning_threshold = Float(
        0.1,
        help="""
        Warn user with flashing lights when memory usage is within this fraction
        memory limit.

        For example, if memory limit is 128MB, `mem_warning_threshold` is 0.1,
        we will start warning the user when they use (128 - (128 * 0.1)) MB.

        Set to 0 to disable warning.
        """,
        config=True
    )

    mem_limit = Int(
        0,
        config=True,
        help="""
        Memory limit to display to the user, in bytes.

        Note that this does not actually limit the user's memory usage!

        Defaults to reading from the `MEM_LIMIT` environment variable. If
        set to 0, no memory limit is displayed.
        """
    )

    @default('mem_limit')
    def _mem_limit_default(self):
        return int(os.environ.get('MEM_LIMIT', 0))

    disk_warning_threshold = Float(
        0.1,
        help="""
        Warn user with flashing lights when home directory free space drops
        below this fraction the home directory size.

        For example, if $HOME is 1024 MB, warn when the free space drops below
        0.1 * 1024 = 102 MB.

        Defaults to 0.1 (10%).

        Set to 0 to disable the warning.
        """,
        config=True
    )


    disk_path = Unicode(
        help="""
        Path for which to monitor free space.

        Defaults to the contents of the `HOME` environment variable.
        """
        config=True
    )

    @default('disk_path')
    def _disk_path_default(self):
        return os.environ.get('HOME', '/')


def load_jupyter_server_extension(nbapp):
    """
    Called during notebook start
    """
    resuseconfig = ResourceUseDisplay(parent=nbapp)
    nbapp.web_app.settings['nbresuse_display_config'] = resuseconfig
    route_pattern = url_path_join(nbapp.web_app.settings['base_url'], '/metrics')
    nbapp.web_app.add_handlers('.*', [(route_pattern, MetricsHandler)])

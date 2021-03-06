"""
homeassistant.components.downloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to download files.
"""
import os
import logging
import re
import threading

from homeassistant.helpers import validate_config
from homeassistant.util import sanitize_filename

DOMAIN = "downloader"
DEPENDENCIES = []

SERVICE_DOWNLOAD_FILE = "download_file"

ATTR_URL = "url"
ATTR_SUBDIR = "subdir"

CONF_DOWNLOAD_DIR = 'download_dir'


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Listens for download events to download files. """

    logger = logging.getLogger(__name__)

    try:
        import requests
    except ImportError:
        logger.exception(("Failed to import requests. "
                          "Did you maybe not execute 'pip install requests'?"))

        return False

    if not validate_config(config, {DOMAIN: [CONF_DOWNLOAD_DIR]}, logger):
        return False

    download_path = config[DOMAIN][CONF_DOWNLOAD_DIR]

    if not os.path.isdir(download_path):

        logger.error(
            "Download path %s does not exist. File Downloader not active.",
            download_path)

        return False

    def download_file(service):
        """ Starts thread to download file specified in the url. """

        if ATTR_URL not in service.data:
            logger.error("Service called but 'url' parameter not specified.")
            return

        def do_download():
            """ Downloads the file. """
            try:
                url = service.data[ATTR_URL]

                subdir = service.data.get(ATTR_SUBDIR)

                if subdir:
                    subdir = sanitize_filename(subdir)

                final_path = None

                req = requests.get(url, stream=True, timeout=10)

                if req.status_code == 200:
                    filename = None

                    if 'content-disposition' in req.headers:
                        match = re.findall(r"filename=(\S+)",
                                           req.headers['content-disposition'])

                        if len(match) > 0:
                            filename = match[0].strip("'\" ")

                    if not filename:
                        filename = os.path.basename(
                            url).strip()

                    if not filename:
                        filename = "ha_download"

                    # Remove stuff to ruin paths
                    filename = sanitize_filename(filename)

                    # Do we want to download to subdir, create if needed
                    if subdir:
                        subdir_path = os.path.join(download_path, subdir)

                        # Ensure subdir exist
                        if not os.path.isdir(subdir_path):
                            os.makedirs(subdir_path)

                        final_path = os.path.join(subdir_path, filename)

                    else:
                        final_path = os.path.join(download_path, filename)

                    path, ext = os.path.splitext(final_path)

                    # If file exist append a number.
                    # We test filename, filename_2..
                    tries = 1
                    final_path = path + ext
                    while os.path.isfile(final_path):
                        tries += 1

                        final_path = "{}_{}.{}".format(path, tries, ext)

                    logger.info("%s -> %s", url, final_path)

                    with open(final_path, 'wb') as fil:
                        for chunk in req.iter_content(1024):
                            fil.write(chunk)

                    logger.info("Downloading of %s done", url)

            except requests.exceptions.ConnectionError:
                logger.exception("ConnectionError occured for %s", url)

                # Remove file if we started downloading but failed
                if final_path and os.path.isfile(final_path):
                    os.remove(final_path)

        threading.Thread(target=do_download).start()

    hass.services.register(DOMAIN, SERVICE_DOWNLOAD_FILE,
                           download_file)

    return True

# -*- coding: utf-8 -*-
__title__ = 'subliminal'
__version__ = '2.1.0.dev'
__short_version__ = '.'.join(__version__.split('.')[:2])
__author__ = 'Antoine Bertin'
__license__ = 'MIT'
__copyright__ = 'Copyright 2016, Antoine Bertin'

import logging
import traceback

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.error("DEBUG: entering subliminal.__init__")

try:
    from .core import (AsyncProviderPool, ProviderPool, check_video, download_best_subtitles, download_subtitles,
                       list_subtitles, refine, save_subtitles, scan_video, scan_videos)
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after core")
try:
    from .cache import region
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after cache")

try:
    from .exceptions import Error, ProviderError
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after exceptions")
try:
    from .extensions import provider_manager, refiner_manager
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after extensions")
try:
    from .providers import Provider
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after after providers")
try:
    from .score import compute_score, get_scores
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after score")
try:
    from .subtitle import SUBTITLE_EXTENSIONS, Subtitle
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after subtitle")
try:
    from .video import VIDEO_EXTENSIONS, Episode, Movie, Video
except:
    logger.exception(traceback.format_exc())

logger.error("DEBUG: after video")

#logging.getLogger(__name__).addHandler(logging.NullHandler())

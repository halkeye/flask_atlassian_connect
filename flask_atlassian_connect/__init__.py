import logging

logger = logging.getLogger('flask_atlassian_connect')
logger.addHandler(logging.StreamHandler())
if logger.level == logging.NOTSET:
    logger.setLevel(logging.WARN)

__version__ = '0.0.2'
__url__ = 'https://github.com/halkeye/ac-flask'
__author__ = 'Gavin Mogan'
__email__ = 'opensource@gavinmogan.com'

from .base import AtlassianConnect  # NOQA: E402, F401, C0413

__version__ = '0.0.2'
__url__ = 'https://github.com/halkeye/flask_atlassian_connect'
__author__ = 'Gavin Mogan'
__email__ = 'opensource@gavinmogan.com'
__all__ = ['AtlassianConnect', 'AtlassianConnectClient']

from .base import AtlassianConnect  # NOQA: E402, F401, C0413
from .client import AtlassianConnectClient  # NOQA: E402, F401, C0413

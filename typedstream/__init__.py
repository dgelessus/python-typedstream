# "Unused" imports and star imports are ok in __init__.py.
from .stream import * # noqa: F401, F403
from .archiver import * # noqa: F401, F403

# The .classes and .structs modules are normally not used directly,
# but it's important that they are imported,
# so that their classes are registered with KnownArchivedObject and KnownStruct.
from . import classes # noqa: F401
from . import structs # noqa: F401

__version__ = "0.0.1.dev"

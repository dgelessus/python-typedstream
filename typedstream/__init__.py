# "Unused" imports and star imports are ok in __init__.py.
from .stream import InvalidTypedStreamError # noqa: F401
from .archiver import * # noqa: F401, F403

# .types and its submodules are normally not used directly,
# but it's important that they are imported,
# so that their classes are registered with KnownArchivedObject and KnownStruct.
from . import types # noqa: F401

__version__ = "0.0.1.dev"

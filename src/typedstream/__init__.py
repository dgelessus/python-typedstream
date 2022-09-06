# This file is part of the python-typedstream library.
# Copyright (C) 2020 dgelessus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


# "Unused" imports and star imports are ok in __init__.py.
from .stream import InvalidTypedStreamError # noqa: F401
from .archiving import * # noqa: F401, F403

# .types and its submodules are normally not used directly,
# but it's important that they are imported,
# so that their classes are registered with KnownArchivedObject and KnownStruct.
from . import types # noqa: F401

__version__ = "0.0.1.dev"

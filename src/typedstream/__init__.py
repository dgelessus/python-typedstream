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

# To release a new version:
# * Remove the .dev suffix from the version number in this file.
# * Update the changelog in the README.md (rename the "next version" section to the correct version number).
# * Remove the ``dist`` directory (if it exists) to clean up any old release files.
# * Run ``python3 setup.py sdist bdist_wheel`` to build the release files.
# * Run ``python3 -m twine check dist/*`` to check the release files.
# * Fix any errors reported by the build and/or check steps.
# * Commit the changes to main.
# * Tag the release commit with the version number, prefixed with a "v" (e. g. version 1.2.3 is tagged as v1.2.3).
# * Fast-forward the release branch to the new release commit.
# * Push the main and release branches.
# * Upload the release files to PyPI using ``python3 -m twine upload dist/*``.
# * On the GitHub repo's Releases page, edit the new release tag and add the relevant changelog section from the README.md.

# After releasing:
# * (optional) Remove the build and dist directories from the previous release as they are no longer needed.
# * Bump the version number in this file to the next version and add a .dev suffix.
# * Add a new empty section for the next version to the README.md changelog.
# * Commit and push the changes to main.

__version__ = "0.1.1.dev"

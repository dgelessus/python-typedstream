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


import pathlib
import unittest

import typedstream.archiving
import typedstream.stream


DATA_DIR = pathlib.Path(__file__).parent / "data"
READ_TEST_FILE_NAMES = [
	"Emacs.clr",
	"Empty2D macOS 10.14.gcx",
	"Empty2D macOS 13.gcx",
]


class TypedstreamReadTests(unittest.TestCase):
	def test_read_stream(self) -> None:
		"""All the test files can be read as a low-level stream."""
		
		for name in READ_TEST_FILE_NAMES:
			with self.subTest(name=name):
				with typedstream.stream.TypedStreamReader.open(DATA_DIR / name) as ts:
					for _ in ts:
						pass
	
	def test_read_unarchive(self) -> None:
		"""All the test files can be unarchived into objects."""
		
		for name in READ_TEST_FILE_NAMES:
			with self.subTest(name=name):
				with typedstream.archiving.Unarchiver.open(DATA_DIR / name) as unarchiver:
					unarchiver.decode_all()


if __name__ == "__main__":
	unittest.main()

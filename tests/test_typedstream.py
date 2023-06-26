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
import typedstream.types.foundation


DATA_DIR = pathlib.Path(__file__).parent / "data"
READ_TEST_FILE_NAMES = [
	"Emacs.clr",
	"Empty2D macOS 10.14.gcx",
	"Empty2D macOS 13.gcx",
]

STRING_TEST_DATA = b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x08NSString\x01\x84\x84\x08NSObject\x00\x85\x84\x01+\x0cstring value\x86"


class TypedstreamReadTests(unittest.TestCase):
	def test_read_data_stream(self) -> None:
		"""Some simple test data can be read as a low-level stream."""
		
		with typedstream.stream.TypedStreamReader.from_data(STRING_TEST_DATA) as ts:
			events = list(ts)
		
		self.assertEqual(events, [
			typedstream.stream.BeginTypedValues([b"@"]),
			typedstream.stream.BeginObject(),
			typedstream.stream.SingleClass(name=b"NSString", version=1),
			typedstream.stream.SingleClass(name=b"NSObject", version=0),
			None,
			typedstream.stream.BeginTypedValues([b"+"]),
			b"string value",
			typedstream.stream.EndTypedValues(),
			typedstream.stream.EndObject(),
			typedstream.stream.EndTypedValues(),
		])
	
	def test_read_data_unarchive(self) -> None:
		"""Some simple test data can be unarchived into an object."""
		
		root = typedstream.unarchive_from_data(STRING_TEST_DATA)
		self.assertEqual(type(root), typedstream.types.foundation.NSString)
		self.assertEqual(root.value, "string value")
	
	def test_read_file_stream(self) -> None:
		"""All the test files can be read as a low-level stream."""
		
		for name in READ_TEST_FILE_NAMES:
			with self.subTest(name=name):
				with typedstream.stream.TypedStreamReader.open(DATA_DIR / name) as ts:
					for _ in ts:
						pass
	
	def test_read_file_unarchive(self) -> None:
		"""All the test files can be unarchived into objects."""
		
		for name in READ_TEST_FILE_NAMES:
			with self.subTest(name=name):
				with typedstream.archiving.Unarchiver.open(DATA_DIR / name) as unarchiver:
					unarchiver.decode_all()


class FoundationUnarchiveTests(unittest.TestCase):
	def test_unarchive_nsurl_absolute(self) -> None:
		url = typedstream.unarchive_from_data(b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x05NSURL\x00\x84\x84\x08NSObject\x00\x85\x84\x01c\x00\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+\x1ehttps://example.com/index.html\x86\x86")
		self.assertEqual(type(url), typedstream.types.foundation.NSURL)
		self.assertIs(url.relative_to, None)
		self.assertEqual(url.value, "https://example.com/index.html")
	
	def test_unarchive_nsurl_relative(self) -> None:
		url = typedstream.unarchive_from_data(b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84\x84\x05NSURL\x00\x84\x84\x08NSObject\x00\x85\x84\x01c\x01\x92\x84\x93\x95\x00\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01+\x14https://example.com/\x86\x86\x92\x84\x97\x97\nindex.html\x86\x86")
		self.assertEqual(type(url), typedstream.types.foundation.NSURL)
		self.assertIsInstance(url.relative_to, typedstream.types.foundation.NSURL)
		self.assertIs(url.relative_to.relative_to, None)
		self.assertEqual(url.relative_to.value, "https://example.com/")
		self.assertEqual(url.value, "index.html")


if __name__ == "__main__":
	unittest.main()

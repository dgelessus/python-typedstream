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


import collections
import typing

from .. import advanced_repr
from .. import archiving
from . import _common


@archiving.archived_class
class Object(archiving.KnownArchivedObject):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class List(Object, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			_, count = unarchiver.decode_values_of_types(b"i", b"i")
			if count < 0:
				raise ValueError(f"List element count cannot be negative: {count}")
			self.elements = list(unarchiver.decode_array(b"@", count).elements)
		elif class_version == 1:
			count = unarchiver.decode_value_of_type(b"i")
			if count < 0:
				raise ValueError(f"List element count cannot be negative: {count}")
			
			if count > 0:
				self.elements = list(unarchiver.decode_array(b"@", count).elements)
			else:
				# If the list is empty,
				# the array isn't stored at all.
				self.elements = []
		else:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class HashTable(Object, advanced_repr.AsMultilineStringBase):
	detect_backreferences = False
	
	contents: "collections.OrderedDict[typing.Any, typing.Any]"
	key_type_encoding: bytes
	value_type_encoding: bytes
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			string_type_encoding = b"*"
		elif class_version == 1:
			string_type_encoding = b"%"
		else:
			raise ValueError(f"Unsupported version: {class_version}")
		
		count, self.key_type_encoding, self.value_type_encoding = unarchiver.decode_values_of_types(b"i", string_type_encoding, string_type_encoding)
		if count < 0:
			raise ValueError(f"HashTable element count cannot be negative: {count}")
		
		self.contents = collections.OrderedDict()
		for _ in range(count):
			key = unarchiver.decode_value_of_type(self.key_type_encoding)
			value = unarchiver.decode_value_of_type(self.value_type_encoding)
			self.contents[key] = value
	
	def _as_multiline_string_header_(self) -> str:
		if not self.contents:
			count_desc = "empty"
		elif len(self.contents) == 1:
			count_desc = "1 entry"
		else:
			count_desc = f"{len(self.contents)} entries"
		
		return f"{type(self).__name__}, key/value types {self.key_type_encoding!r}/{self.value_type_encoding!r}, {count_desc}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for key, value in self.contents.items():
			yield from advanced_repr.as_multiline_string(value, prefix=f"{key!r}: ")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(key_type_encoding={self.key_type_encoding!r}, value_type_encoding={self.value_type_encoding!r}, contents={self.contents!r})"


@archiving.archived_class
class StreamTable(HashTable):
	detect_backreferences = False
	
	class _UnarchivedContents(typing.Mapping[typing.Any, typing.Any]):
		archived_contents: typing.Mapping[typing.Any, bytes]
		
		def __init__(self, archived_contents: typing.Mapping[typing.Any, bytes]) -> None:
			super().__init__()
			
			self.archived_contents = archived_contents
		
		def __len__(self) -> int:
			return len(self.archived_contents)
		
		def __iter__(self) -> typing.Iterator[typing.Any]:
			return iter(self.archived_contents)
		
		def keys(self) -> typing.KeysView[typing.Any]:
			return self.archived_contents.keys()
		
		def __getitem__(self, key: typing.Any) -> typing.Any:
			return archiving.unarchive_from_data(self.archived_contents[key])
	
	unarchived_contents: "collections.Mapping[typing.Any, typing.Any]"
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 1:
			raise ValueError(f"Unsupported version: {class_version}")
		
		if self.value_type_encoding != b"!":
			raise ValueError(f"StreamTable values must be ignored, not {self.value_type_encoding!r}")
		
		for key in self.contents:
			assert self.contents[key] is None
			key_again = unarchiver.decode_value_of_type(self.key_type_encoding)
			if key != key_again:
				raise ValueError(f"Expected to read value for key {key}, but found {key_again}")
			self.contents[key] = unarchiver.decode_data_object()
		
		self.unarchived_contents = StreamTable._UnarchivedContents(self.contents)
	
	def _as_multiline_string_header_(self) -> str:
		if not self.unarchived_contents:
			count_desc = "empty"
		elif len(self.unarchived_contents) == 1:
			count_desc = "1 entry"
		else:
			count_desc = f"{len(self.unarchived_contents)} entries"
		
		return f"{type(self).__name__}, {count_desc}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for key, value in self.unarchived_contents.items():
			yield from advanced_repr.as_multiline_string(value, prefix=f"{key!r}: ")


@archiving.archived_class
class Storage(Object, advanced_repr.AsMultilineStringBase):
	detect_backreferences = False
	
	element_type_encoding: bytes
	element_size: int
	elements: typing.List[typing.Any]
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.element_type_encoding, self.element_size, _, count = unarchiver.decode_values_of_types(b"*", b"i", b"i", b"i")
			if count < 0:
				raise ValueError(f"Storage element count cannot be negative: {count}")
			self.elements = list(unarchiver.decode_array(self.element_type_encoding, count).elements)
		elif class_version == 1:
			self.element_type_encoding, self.element_size, count = unarchiver.decode_values_of_types(b"%", b"i", b"i")
			if count < 0:
				raise ValueError(f"Storage element count cannot be negative: {count}")
			
			if count > 0:
				self.elements = list(unarchiver.decode_array(self.element_type_encoding, count).elements)
			else:
				# If the Storage is empty,
				# the array isn't stored at all.
				self.elements = []
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_header_(self) -> str:
		if not self.elements:
			count_desc = "empty"
		elif len(self.elements) == 1:
			count_desc = "1 element"
		else:
			count_desc = f"{len(self.elements)} elements"
		
		return f"{type(self).__name__}, element type {self.element_type_encoding!r} ({self.element_size!r} bytes each), {count_desc}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for element in self.elements:
			yield from advanced_repr.as_multiline_string(element)
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(element_type_encoding={self.element_type_encoding!r}, element_size={self.element_size!r}, elements={self.elements!r})"

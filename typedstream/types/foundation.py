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
import datetime
import typing

from .. import advanced_repr
from .. import archiver
from . import _common


@archiver.archived_class
class NSObject(archiver.KnownArchivedObject):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSData(NSObject):
	data: bytes
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.data = unarchiver.decode_data_object()
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.data!r})"


@archiver.archived_class
class NSMutableData(NSData):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSDate(NSObject):
	ABSOLUTE_REFERENCE_DATE: typing.ClassVar[datetime.datetime] = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
	
	absolute_reference_date_offset: float
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.absolute_reference_date_offset = unarchiver.decode_value_of_type(b"d")
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	@property
	def value(self) -> datetime.datetime:
		return type(self).ABSOLUTE_REFERENCE_DATE + datetime.timedelta(seconds=self.absolute_reference_date_offset)
	
	def __str__(self) -> str:
		return f"<{type(self).__name__}: {self.value}>"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(absolute_reference_date_offset={self.absolute_reference_date_offset})"


@archiver.archived_class
class NSString(NSObject):
	value: str
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 1:
			self.value = unarchiver.decode_value_of_type(b"+").decode("utf-8")
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.value!r})"


@archiver.archived_class
class NSMutableString(NSString):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 1:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSValue(NSObject, advanced_repr.AsMultilineStringBase):
	type_encoding: bytes
	value: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.type_encoding = unarchiver.decode_value_of_type(b"*")
			self.value = unarchiver.decode_value_of_type(self.type_encoding)
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		value_it = iter(advanced_repr.as_multiline_string(self.value, calling_self=self, state=state))
		yield f"{type(self).__name__}, type {self.type_encoding!r}: " + next(value_it, "")
		for line in value_it:
			yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(type_encoding={self.type_encoding!r}, value={self.value!r})"


@archiver.archived_class
class NSNumber(NSValue):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSArray(NSObject, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_value_of_type(b"i")
			if count < 0:
				raise ValueError(f"NSArray element count cannot be negative: {count}")
			self.elements = []
			for _ in range(count):
				self.elements.append(unarchiver.decode_value_of_type(b"@"))
		else:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSMutableArray(NSArray):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSSet(NSObject, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_value_of_type(b"I")
			self.elements = []
			for _ in range(count):
				self.elements.append(unarchiver.decode_value_of_type(b"@"))
		else:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSMutableSet(NSSet):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSDictionary(NSObject, advanced_repr.AsMultilineStringBase):
	contents: "collections.OrderedDict[typing.Any, typing.Any]"
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_value_of_type(b"i")
			if count < 0:
				raise ValueError(f"NSDictionary element count cannot be negative: {count}")
			self.contents = collections.OrderedDict()
			for _ in range(count):
				key = unarchiver.decode_value_of_type(b"@")
				value = unarchiver.decode_value_of_type(b"@")
				self.contents[key] = value
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.contents:
			count_desc = "empty"
		elif len(self.contents) == 1:
			count_desc = "1 entry:"
		else:
			count_desc = f"{len(self.contents)} entries:"
		
		yield f"{type(self).__name__}, {count_desc}"
		
		for key, value in self.contents.items():
			value_it = iter(advanced_repr.as_multiline_string(value, calling_self=self, state=state))
			yield f"\t{key!r}: " + next(value_it, "")
			for line in value_it:
				yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.contents!r})"


@archiver.archived_class
class NSMutableDictionary(NSDictionary):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")

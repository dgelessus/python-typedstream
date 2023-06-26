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
from .. import archiving
from . import _common


@archiving.struct_class
class NSPoint(archiving.KnownStruct):
	struct_name = b"_NSPoint"
	field_encodings = [b"f", b"f"]
	
	x: float
	y: float
	
	def __init__(self, x: float, y: float) -> None:
		super().__init__()
		
		self.x = x
		self.y = y
	
	def __str__(self) -> str:
		x = int(self.x) if int(self.x) == self.x else self.x
		y = int(self.y) if int(self.y) == self.y else self.y
		return f"{{{x}, {y}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(x={self.x!r}, y={self.y!r})"


@archiving.struct_class
class NSSize(archiving.KnownStruct):
	struct_name = b"_NSSize"
	field_encodings = [b"f", b"f"]
	
	width: float
	height: float
	
	def __init__(self, width: float, height: float) -> None:
		super().__init__()
		
		self.width = width
		self.height = height
	
	def __str__(self) -> str:
		width = int(self.width) if int(self.width) == self.width else self.width
		height = int(self.height) if int(self.height) == self.height else self.height
		return f"{{{width}, {height}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(width={self.width!r}, height={self.height!r})"


@archiving.struct_class
class NSRect(archiving.KnownStruct):
	struct_name = b"_NSRect"
	field_encodings = [NSPoint.encoding, NSSize.encoding]
	
	origin: NSPoint
	size: NSSize
	
	def __init__(self, origin: NSPoint, size: NSSize) -> None:
		super().__init__()
		
		self.origin = origin
		self.size = size
	
	@classmethod
	def make(cls, x: float, y: float, width: float, height: float) -> "NSRect":
		return cls(NSPoint(x, y), NSSize(width, height))
	
	def __str__(self) -> str:
		return f"{{{self.origin}, {self.size}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(origin={self.origin!r}, size={self.size!r})"


@archiving.archived_class
class NSObject(archiving.KnownArchivedObject):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSData(NSObject):
	data: bytes
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.data = unarchiver.decode_data_object()
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.data!r})"


@archiving.archived_class
class NSMutableData(NSData):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSDate(NSObject):
	ABSOLUTE_REFERENCE_DATE: typing.ClassVar[datetime.datetime] = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
	
	absolute_reference_date_offset: float
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.absolute_reference_date_offset = unarchiver.decode_value_of_type(b"d")
	
	@property
	def value(self) -> datetime.datetime:
		return type(self).ABSOLUTE_REFERENCE_DATE + datetime.timedelta(seconds=self.absolute_reference_date_offset)
	
	def __str__(self) -> str:
		return f"<{type(self).__name__}: {self.value}>"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(absolute_reference_date_offset={self.absolute_reference_date_offset})"


@archiving.archived_class
class NSString(NSObject):
	value: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 1:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.value = unarchiver.decode_value_of_type(b"+").decode("utf-8")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.value!r})"


@archiving.archived_class
class NSMutableString(NSString):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 1:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSURL(NSObject):
	relative_to: "typing.Optional[NSURL]"
	value: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		is_relative = unarchiver.decode_value_of_type(b"c")
		if is_relative == 0:
			self.relative_to = None
		elif is_relative == 1:
			self.relative_to = unarchiver.decode_value_of_type(NSURL)
		else:
			raise ValueError(f"Unexpected value for boolean: {is_relative}")
		
		self.value = unarchiver.decode_value_of_type(NSString).value
	
	def __repr__(self) -> str:
		if self.relative_to is None:
			return f"{type(self).__name__}({self.value!r})"
		else:
			return f"{type(self).__name__}(relative_to={self.relative_to!r}, value={self.value!r})"


@archiving.archived_class
class NSValue(NSObject, advanced_repr.AsMultilineStringBase):
	detect_backreferences = False
	
	type_encoding: bytes
	value: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.type_encoding = unarchiver.decode_value_of_type(b"*")
		self.value = unarchiver.decode_value_of_type(self.type_encoding)
	
	def _as_multiline_string_(self) -> typing.Iterable[str]:
		yield from advanced_repr.as_multiline_string(self.value, prefix=f"{type(self).__name__}, type {self.type_encoding!r}: ")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(type_encoding={self.type_encoding!r}, value={self.value!r})"


@archiving.archived_class
class NSNumber(NSValue):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSArray(NSObject, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		count = unarchiver.decode_value_of_type(b"i")
		if count < 0:
			raise ValueError(f"NSArray element count cannot be negative: {count}")
		self.elements = []
		for _ in range(count):
			self.elements.append(unarchiver.decode_value_of_type(b"@"))


@archiving.archived_class
class NSMutableArray(NSArray):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSSet(NSObject, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		count = unarchiver.decode_value_of_type(b"I")
		self.elements = []
		for _ in range(count):
			self.elements.append(unarchiver.decode_value_of_type(b"@"))


@archiving.archived_class
class NSMutableSet(NSSet):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSDictionary(NSObject, advanced_repr.AsMultilineStringBase):
	detect_backreferences = False
	
	contents: "collections.OrderedDict[typing.Any, typing.Any]"
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		count = unarchiver.decode_value_of_type(b"i")
		if count < 0:
			raise ValueError(f"NSDictionary element count cannot be negative: {count}")
		self.contents = collections.OrderedDict()
		for _ in range(count):
			key = unarchiver.decode_value_of_type(b"@")
			value = unarchiver.decode_value_of_type(b"@")
			self.contents[key] = value
	
	def _as_multiline_string_header_(self) -> str:
		if not self.contents:
			count_desc = "empty"
		elif len(self.contents) == 1:
			count_desc = "1 entry"
		else:
			count_desc = f"{len(self.contents)} entries"
		
		return f"{type(self).__name__}, {count_desc}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for key, value in self.contents.items():
			yield from advanced_repr.as_multiline_string(value, prefix=f"{key!r}: ")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.contents!r})"


@archiving.archived_class
class NSMutableDictionary(NSDictionary):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")

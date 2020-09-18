import datetime
import typing

from . import advanced_repr
from . import archiver


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
			length = unarchiver.decode_typed_values(b"i")
			self.data = unarchiver.decode_typed_values(f"[{length}c]".encode("ascii"))
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
			self.absolute_reference_date_offset = unarchiver.decode_typed_values(b"d")
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
			self.value = unarchiver.decode_typed_values(b"+").decode("utf-8")
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
			self.type_encoding = unarchiver.decode_typed_values(b"*")
			self.value = unarchiver.decode_typed_values(self.type_encoding)
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		value_it = iter(advanced_repr.as_multiline_string(self.value, calling_self=self, state=state))
		yield f"{type(self).__name__}, type {self.type_encoding}: " + next(value_it, "")
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
class NSArray(NSObject, advanced_repr.AsMultilineStringBase):
	elements: typing.List[typing.Any]
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_typed_values(b"i")
			self.elements = []
			for _ in range(count):
				self.elements.append(unarchiver.decode_typed_values(b"@"))
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.elements:
			count_desc = "empty"
		elif len(self.elements) == 1:
			count_desc = "1 element:"
		else:
			count_desc = f"{len(self.elements)} elements:"
		
		yield f"{type(self).__name__}, {count_desc}"
		
		for element in self.elements:
			for line in advanced_repr.as_multiline_string(element, calling_self=self, state=state):
				yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.elements!r})"


@archiver.archived_class
class NSMutableArray(NSArray):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")

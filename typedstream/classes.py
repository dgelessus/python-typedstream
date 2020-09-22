import collections
import datetime
import enum
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
			if length < 0:
				raise ValueError(f"NSData length cannot be negative: {length}")
			self.data = unarchiver.decode_array(b"c", length)
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


class _ArraySetBase(advanced_repr.AsMultilineStringBase):
	elements: typing.List[typing.Any]
	
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
class NSArray(NSObject, _ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_typed_values(b"i")
			if count < 0:
				raise ValueError(f"NSArray element count cannot be negative: {count}")
			self.elements = []
			for _ in range(count):
				self.elements.append(unarchiver.decode_typed_values(b"@"))
		else:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSMutableArray(NSArray):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class NSSet(NSObject, _ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			count = unarchiver.decode_typed_values(b"I")
			self.elements = []
			for _ in range(count):
				self.elements.append(unarchiver.decode_typed_values(b"@"))
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
			count = unarchiver.decode_typed_values(b"i")
			if count < 0:
				raise ValueError(f"NSDictionary element count cannot be negative: {count}")
			self.contents = collections.OrderedDict()
			for _ in range(count):
				key = unarchiver.decode_typed_values(b"@")
				value = unarchiver.decode_typed_values(b"@")
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


@archiver.archived_class
class NSColor(NSObject):
	class Kind(enum.Enum):
		CALIBRATED_RGBA = 1
		DEVICE_RGBA = 2
		CALIBRATED_WA = 3
		DEVICE_WA = 4
		DEVICE_CMYKA = 5
		NAMED = 6
	
	class RGBAValue(object):
		red: float
		green: float
		blue: float
		alpha: float
		
		def __init__(self, red: float, green: float, blue: float, alpha: float) -> None:
			super().__init__()
			
			self.red = red
			self.green = green
			self.blue = blue
			self.alpha = alpha
		
		def __str__(self) -> str:
			return f"{self.red}, {self.green}, {self.blue}, {self.alpha}"
		
		def __repr__(self) -> str:
			return f"{type(self).__name__}(red={self.red}, green={self.green}, blue={self.blue}, alpha={self.alpha})"
	
	class WAValue(object):
		white: float
		alpha: float
		
		def __init__(self, white: float, alpha: float) -> None:
			super().__init__()
			
			self.white = white
			self.alpha = alpha
		
		def __str__(self) -> str:
			return f"{self.white}, {self.alpha}"
		
		def __repr__(self) -> str:
			return f"{type(self).__name__}(white={self.white}, alpha={self.alpha})"
	
	class CMYKAValue(object):
		cyan: float
		magenta: float
		yellow: float
		black: float
		alpha: float
		
		def __init__(self, cyan: float, magenta: float, yellow: float, black: float, alpha: float) -> None:
			super().__init__()
			
			self.cyan = cyan
			self.magenta = magenta
			self.yellow = yellow
			self.black = black
			self.alpha = alpha
		
		def __str__(self) -> str:
			return f"{self.cyan}, {self.magenta}, {self.yellow}, {self.black}, {self.alpha}"
		
		def __repr__(self) -> str:
			return f"{type(self).__name__}(cyan={self.cyan}, magenta={self.magenta}, yellow={self.yellow}, black={self.black}, alpha={self.alpha})"
	
	class NamedValue(object):
		group: str
		name: str
		color: "NSColor"
		
		def __init__(self, group: str, name: str, color: "NSColor") -> None:
			super().__init__()
			
			self.group = group
			self.name = name
			self.color = color
		
		def __str__(self) -> str:
			return f"group {self.group!r}, name {self.name!r}, color {self.color}"
		
		def __repr__(self) -> str:
			return f"{type(self).__name__}(group={self.group!r}, name={self.name!r}, color={self.color!r})"
	
	Value = typing.Union["NSColor.RGBAValue", "NSColor.WAValue", "NSColor.CMYKAValue", "NSColor.NamedValue"]
	
	kind: "NSColor.Kind"
	value: "NSColor.Value"
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.kind = NSColor.Kind(unarchiver.decode_typed_values(b"c"))
			if self.kind in {NSColor.Kind.CALIBRATED_RGBA, NSColor.Kind.DEVICE_RGBA}:
				red, green, blue, alpha = unarchiver.decode_typed_values(b"f", b"f", b"f", b"f")
				self.value = NSColor.RGBAValue(red, green, blue, alpha)
			elif self.kind in {NSColor.Kind.CALIBRATED_WA, NSColor.Kind.DEVICE_WA}:
				white, alpha = unarchiver.decode_typed_values(b"f", b"f")
				self.value = NSColor.WAValue(white, alpha)
			elif self.kind == NSColor.Kind.DEVICE_CMYKA:
				cyan, magenta, yellow, black, alpha = unarchiver.decode_typed_values(b"f", b"f", b"f", b"f", b"f")
				self.value = NSColor.CMYKAValue(cyan, magenta, yellow, black, alpha)
			elif self.kind == NSColor.Kind.NAMED:
				group, name, color = unarchiver.decode_typed_values(b"@", b"@", b"@")
				if not isinstance(group, NSString):
					raise TypeError(f"Named NSColor group name must be a NSString, not {type(group)}")
				if not isinstance(name, NSString):
					raise TypeError(f"Named NSColor name must be a NSString, not {type(name)}")
				if not isinstance(color, NSColor):
					raise TypeError(f"Named NSColor color must be a NSColor, not {type(name)}")
				self.value = NSColor.NamedValue(group.value, name.value, color)
			else:
				raise AssertionError(f"Unhandled NSColor kind: {self.kind}")
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def __str__(self) -> str:
		return f"<{type(self).__name__} {self.kind.name}: {self.value}>"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(kind={self.kind.name}, value={self.value!r})"


@archiver.archived_class
class NSFont(NSObject):
	name: str
	size: float
	flags_unknown: typing.Tuple[int, int, int, int]
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version in {21, 30}:
			name = unarchiver.decode_property_list()
			if not isinstance(name, str):
				raise TypeError(f"Font name must be a string, not {type(name)}")
			self.name = name
			self.size = unarchiver.decode_typed_values(b"f")
			self.flags_unknown = (
				unarchiver.decode_typed_values(b"c"),
				unarchiver.decode_typed_values(b"c"),
				unarchiver.decode_typed_values(b"c"),
				unarchiver.decode_typed_values(b"c"),
			)
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def __repr__(self) -> str:
		flags_repr = ", ".join([f"0x{flag:>02x}" for flag in self.flags_unknown])
		return f"{type(self).__name__}(name={self.name!r}, size={self.size!r}, flags_unknown=({flags_repr}))"

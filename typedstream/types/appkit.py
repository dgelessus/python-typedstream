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
import enum
import typing

from .. import advanced_repr
from .. import archiver
from . import _common
from . import foundation


@archiver.struct_class
class NSPoint(archiver.KnownStruct):
	struct_name = b"_NSPoint"
	field_encodings = [b"f", b"f"]
	
	x: float
	y: float
	
	def __init__(self, x: float, y: float) -> None:
		super().__init__()
		
		self.x = x
		self.y = y
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(x={self.x!r}, y={self.y!r})"


@archiver.struct_class
class NSSize(archiver.KnownStruct):
	struct_name = b"_NSSize"
	field_encodings = [b"f", b"f"]
	
	width: float
	height: float
	
	def __init__(self, width: float, height: float) -> None:
		super().__init__()
		
		self.width = width
		self.height = height
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(width={self.width!r}, height={self.height!r})"


@archiver.struct_class
class NSRect(archiver.KnownStruct):
	struct_name = b"_NSRect"
	field_encodings = [NSPoint.encoding, NSSize.encoding]
	
	origin: NSPoint
	size: NSSize
	
	def __init__(self, origin: NSPoint, size: NSSize) -> None:
		super().__init__()
		
		self.origin = origin
		self.size = size
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(origin={self.origin!r}, size={self.size!r})"


@archiver.archived_class
class NSColor(foundation.NSObject):
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
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.kind = NSColor.Kind(unarchiver.decode_value_of_type(b"c"))
		if self.kind in {NSColor.Kind.CALIBRATED_RGBA, NSColor.Kind.DEVICE_RGBA}:
			red, green, blue, alpha = unarchiver.decode_values_of_types(b"f", b"f", b"f", b"f")
			self.value = NSColor.RGBAValue(red, green, blue, alpha)
		elif self.kind in {NSColor.Kind.CALIBRATED_WA, NSColor.Kind.DEVICE_WA}:
			white, alpha = unarchiver.decode_values_of_types(b"f", b"f")
			self.value = NSColor.WAValue(white, alpha)
		elif self.kind == NSColor.Kind.DEVICE_CMYKA:
			cyan, magenta, yellow, black, alpha = unarchiver.decode_values_of_types(b"f", b"f", b"f", b"f", b"f")
			self.value = NSColor.CMYKAValue(cyan, magenta, yellow, black, alpha)
		elif self.kind == NSColor.Kind.NAMED:
			group, name, color = unarchiver.decode_values_of_types(b"@", b"@", b"@")
			if not isinstance(group, foundation.NSString):
				raise TypeError(f"Named NSColor group name must be a NSString, not {type(group)}")
			if not isinstance(name, foundation.NSString):
				raise TypeError(f"Named NSColor name must be a NSString, not {type(name)}")
			if not isinstance(color, NSColor):
				raise TypeError(f"Named NSColor color must be a NSColor, not {type(name)}")
			self.value = NSColor.NamedValue(group.value, name.value, color)
		else:
			raise AssertionError(f"Unhandled NSColor kind: {self.kind}")
	
	def __str__(self) -> str:
		return f"<{type(self).__name__} {self.kind.name}: {self.value}>"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(kind={self.kind.name}, value={self.value!r})"


@archiver.archived_class
class NSCustomObject(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	class_name: str
	object: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsuppored version: {class_version}")
		
		class_name, obj = unarchiver.decode_values_of_types(b"@", b"@")
		if not isinstance(class_name, foundation.NSString):
			raise TypeError(f"Class name must be a NSString, not {type(class_name)}")
		self.class_name = class_name.value
		self.object = obj
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		it = iter(advanced_repr.as_multiline_string(self.object, calling_self=self, state=state))
		yield f"{type(self).__name__}, class {self.class_name}, object: " + next(it, "")
		for line in it:
			yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(class_name={self.class_name!r}, object={self.object!r})"


@archiver.archived_class
class NSFont(foundation.NSObject):
	name: str
	size: float
	flags_unknown: typing.Tuple[int, int, int, int]
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version not in {21, 30}:
			raise ValueError(f"Unsupported version: {class_version}")
		
		name = unarchiver.decode_property_list()
		if not isinstance(name, str):
			raise TypeError(f"Font name must be a string, not {type(name)}")
		self.name = name
		self.size = unarchiver.decode_value_of_type(b"f")
		self.flags_unknown = (
			unarchiver.decode_value_of_type(b"c"),
			unarchiver.decode_value_of_type(b"c"),
			unarchiver.decode_value_of_type(b"c"),
			unarchiver.decode_value_of_type(b"c"),
		)
	
	def __repr__(self) -> str:
		flags_repr = ", ".join([f"0x{flag:>02x}" for flag in self.flags_unknown])
		return f"{type(self).__name__}(name={self.name!r}, size={self.size!r}, flags_unknown=({flags_repr}))"


@archiver.archived_class
class NSIBObjectData(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	root: typing.Any
	object_parents: "collections.OrderedDict[typing.Any, typing.Any]"
	object_names: "collections.OrderedDict[typing.Any, str]"
	unknown_set: typing.Any
	connections: typing.List[typing.Any]
	unknown_object: typing.Any
	object_ids: "collections.OrderedDict[typing.Any, int]"
	next_object_id: int
	target_framework: str
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 224:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.root = unarchiver.decode_value_of_type(b"@")
		
		parents_count = unarchiver.decode_value_of_type(b"i")
		self.object_parents = collections.OrderedDict()
		for i in range(parents_count):
			child, parent = unarchiver.decode_values_of_types(b"@", b"@")
			if child in self.object_parents:
				raise ValueError(f"Duplicate object parent entry {i} - this object already has a parent")
			self.object_parents[child] = parent
		
		names_count = unarchiver.decode_value_of_type(b"i")
		self.object_names = collections.OrderedDict()
		for i in range(names_count):
			obj, name = unarchiver.decode_values_of_types(b"@", b"@")
			if obj in self.object_names:
				raise ValueError(f"Duplicate object name entry {i} - this object already has a name")
			if not isinstance(name, foundation.NSString):
				raise TypeError(f"Object name must be a NSString, not {type(name)}")
			self.object_names[obj] = name.value
		
		self.unknown_set = unarchiver.decode_value_of_type(b"@")
		
		connections = unarchiver.decode_value_of_type(b"@")
		if not isinstance(connections, foundation.NSArray):
			raise TypeError(f"Connetions must be a NSArray, not {type(connections)}")
		self.connections = connections.elements
		
		self.unknown_object = unarchiver.decode_value_of_type(b"@")
		
		oids_count = unarchiver.decode_value_of_type(b"i")
		self.object_ids = collections.OrderedDict()
		for i in range(oids_count):
			obj, oid = unarchiver.decode_values_of_types(b"@", b"i")
			if obj in self.object_ids:
				raise ValueError(f"Duplicate object ID entry {i} - this object already has an ID")
			self.object_ids[obj] = oid
		
		self.next_object_id = unarchiver.decode_value_of_type(b"i")
		
		unknown_int = unarchiver.decode_value_of_type(b"i")
		if unknown_int != 0:
			raise ValueError(f"Unknown int field is not 0: {unknown_int}")
		
		target_framework = unarchiver.decode_value_of_type(b"@")
		if not isinstance(target_framework, foundation.NSString):
			raise TypeError(f"Target framework must be a NSString, not {type(target_framework)}")
		self.target_framework = target_framework.value
	
	def _oid_repr(self, obj: typing.Any) -> str:
		try:
			oid = self.object_ids[obj]
		except KeyError:
			return "<missing OID!>"
		else:
			return f"#{oid}"
	
	def _object_desc(self, obj: typing.Any) -> str:
		desc = _common.object_class_name(obj)
		
		try:
			name = self.object_names[obj]
		except KeyError:
			pass
		else:
			desc += f" {name!r}"
		
		return f"{self._oid_repr(obj)} ({desc})"
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		yield f"{type(self).__name__}, target framework {self.target_framework!r}:"
		
		yield f"\t{len(self.object_ids)} objects:"
		for obj, oid in self.object_ids.items():
			obj_it = iter(advanced_repr.as_multiline_string(obj, calling_self=self, state=state))
			yield f"\t\t#{oid}: {next(obj_it)}"
			for line in obj_it:
				yield "\t\t" + line
		
		yield f"\tnext object ID: #{self.next_object_id}"
		yield f"\troot object: {self._object_desc(self.root)}"
		
		yield f"\t{len(self.object_parents)} object parents:"
		for child, parent in self.object_parents.items():
			yield f"\t\t{self._object_desc(child)} --> parent {self._object_desc(parent)}"
		
		yield f"\t{len(self.object_names)} object names:"
		for obj in self.object_names:
			yield f"\t\t{self._object_desc(obj)}" # _object_desc includes the object name
		
		unknown_set_it = iter(advanced_repr.as_multiline_string(self.unknown_set, calling_self=self, state=state))
		yield f"\tunknown set: {next(unknown_set_it)}"
		for line in unknown_set_it:
			yield "\t" + line
		
		yield f"\t{len(self.connections)} connections:"
		for connection in self.connections:
			yield f"\t\t{self._object_desc(connection)}"
		
		unknown_object_it = iter(advanced_repr.as_multiline_string(self.unknown_object, calling_self=self, state=state))
		yield f"\tunknown object: {next(unknown_object_it)}"
		for line in unknown_object_it:
			yield "\t" + line
	
	def __repr__(self) -> str:
		object_parents_repr = "{" + ", ".join(f"{self._oid_repr(child)}: {self._oid_repr(parent)}" for child, parent in self.object_parents.items()) + "}"
		object_names_repr = "{" + ", ".join(f"{self._oid_repr(obj)}: {name!r}" for obj, name in self.object_names.items()) + "}"
		connections_repr = "[" + ", ".join(f"{self._oid_repr(connection)}" for connection in self.connections) + "]"
		object_ids_repr = "{" + ", ".join(f"<{_common.object_class_name(obj)}>: {oid}" for obj, oid in self.object_ids.items()) + "}"
		
		return f"<{type(self).__name__}: root={self._oid_repr(self.root)}, object_parents={object_parents_repr}, object_names={object_names_repr}, unknown_set={self.unknown_set!r}, connections={connections_repr}, unknown_object={self.unknown_object!r}, object_ids={object_ids_repr}, next_object_id={self.next_object_id}, target_framework={self.target_framework!r}>"

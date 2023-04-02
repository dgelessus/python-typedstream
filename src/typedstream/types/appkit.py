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
from .. import archiving
from .. import stream
from . import foundation


def _object_class_name(obj: typing.Any) -> str:
	if isinstance(obj, (NSClassSwapper, NSCustomObject)):
		return obj.class_name
	else:
		return archiving._object_class_name(obj)


class NSBezierPathElement(enum.Enum):
	move_to = 0
	line_to = 1
	curve_to = 2
	close_path = 3


class NSLineCapStyle(enum.Enum):
	butt = 0
	round = 1
	square = 2


class NSLineJoinStyle(enum.Enum):
	miter = 0
	round = 1
	bevel = 2


class NSWindingRule(enum.Enum):
	non_zero = 0
	even_odd = 1


@archiving.archived_class
class NSBezierPath(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	elements: typing.List[typing.Tuple[NSBezierPathElement, foundation.NSPoint]]
	winding_rule: NSWindingRule
	line_cap_style: NSLineCapStyle
	line_join_style: NSLineJoinStyle
	line_width: float
	miter_limit: float
	flatness: float
	line_dash: typing.Optional[typing.Tuple[float, typing.List[float]]]
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 524:
			raise ValueError(f"Unsupported version: {class_version}")
		
		element_count = unarchiver.decode_value_of_type(b"i")
		self.elements = []
		for _ in range(element_count):
			element, x, y = unarchiver.decode_values_of_types(b"c", b"f", b"f")
			self.elements.append((NSBezierPathElement(element), foundation.NSPoint(x, y)))
		
		(
			winding_rule, line_cap_style, line_join_style,
			self.line_width, self.miter_limit, self.flatness,
			line_dash_count,
		) = unarchiver.decode_values_of_types(
			b"i", b"i", b"i",
			b"f", b"f", b"f",
			b"i",
		)
		
		self.winding_rule = NSWindingRule(winding_rule)
		self.line_cap_style = NSLineCapStyle(line_cap_style)
		self.line_join_style = NSLineJoinStyle(line_join_style)
		
		if line_dash_count > 0:
			phase = unarchiver.decode_value_of_type(b"f")
			pattern = []
			for _ in range(line_dash_count):
				pattern.append(unarchiver.decode_value_of_type(b"f"))
			
			self.line_dash = (phase, pattern)
		else:
			self.line_dash = None
	
	def _as_multiline_string_header_(self) -> str:
		return type(self).__name__
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield f"winding rule: {self.winding_rule.name}"
		yield f"line cap style: {self.line_cap_style.name}"
		yield f"line join style: {self.line_join_style.name}"
		yield f"line width: {self.line_width}"
		yield f"miter limit: {self.miter_limit}"
		yield f"flatness: {self.flatness}"
		if self.line_dash is not None:
			phase, pattern = self.line_dash
			yield f"line dash: phase {phase}, pattern {pattern}"
		
		if self.elements:
			yield f"{len(self.elements)} path elements:"
			for element, point in self.elements:
				yield f"\t{element.name} {point!s}"
		else:
			yield "no path elements"


@archiving.archived_class
class NSClassSwapper(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	class_name: str
	template_class: archiving.Class
	template: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 42:
			raise ValueError(f"Unsupported version: {class_version}")
		
		class_name, self.template_class = unarchiver.decode_values_of_types(foundation.NSString, b"#")
		self.class_name = class_name.value
		
		self.template, superclass = archiving.instantiate_archived_class(self.template_class)
		known_obj: typing.Optional[archiving.KnownArchivedObject]
		if isinstance(self.template, archiving.GenericArchivedObject):
			known_obj = self.template.super_object
		else:
			known_obj = self.template
		
		if known_obj is not None:
			assert superclass is not None
			known_obj.init_from_unarchiver(unarchiver, superclass)
	
	def _allows_extra_data_(self) -> bool:
		return self.template._allows_extra_data_()
	
	def _add_extra_field_(self, field: archiving.TypedGroup) -> None:
		self.template._add_extra_field_(field)
	
	def _as_multiline_string_(self) -> typing.Iterable[str]:
		yield from advanced_repr.as_multiline_string(self.template, prefix=f"{type(self).__name__}, class name {self.class_name!r}, template: ")


@archiving.archived_class
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
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
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
			group, name, color = unarchiver.decode_values_of_types(foundation.NSString, foundation.NSString, NSColor)
			self.value = NSColor.NamedValue(group.value, name.value, color)
		else:
			raise AssertionError(f"Unhandled NSColor kind: {self.kind}")
	
	def __str__(self) -> str:
		return f"<{type(self).__name__} {self.kind.name}: {self.value}>"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(kind={self.kind.name}, value={self.value!r})"


@archiving.archived_class
class NSCustomObject(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	class_name: str
	object: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsuppored version: {class_version}")
		
		class_name, obj = unarchiver.decode_values_of_types(foundation.NSString, b"@")
		self.class_name = class_name.value
		self.object = obj
	
	def _as_multiline_string_(self) -> typing.Iterable[str]:
		header = f"{type(self).__name__}, class {self.class_name}"
		if self.object is None:
			yield header
		else:
			yield from advanced_repr.prefix_lines(
				advanced_repr.as_multiline_string(self.object),
				first=header + ", object: ",
				rest="\t",
			)
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(class_name={self.class_name!r}, object={self.object!r})"


@archiving.archived_class
class NSCustomResource(foundation.NSObject):
	class_name: str
	resource_name: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsuppored version: {class_version}")
		
		class_name, resource_name = unarchiver.decode_values_of_types(foundation.NSString, foundation.NSString)
		self.class_name = class_name.value
		self.resource_name = resource_name.value
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(class_name={self.class_name!r}, resource_name={self.resource_name!r})"


@archiving.archived_class
class NSFont(foundation.NSObject):
	name: str
	size: float
	flags_unknown: typing.Tuple[int, int, int, int]
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
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


@archiving.archived_class
class NSIBObjectData(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	root: typing.Any
	object_parents: "collections.OrderedDict[typing.Any, typing.Any]"
	object_names: "collections.OrderedDict[typing.Any, typing.Optional[str]]"
	unknown_set: typing.Any
	connections: typing.List[typing.Any]
	unknown_object: typing.Any
	object_ids: "collections.OrderedDict[typing.Any, int]"
	next_object_id: int
	swapper_class_names: "collections.OrderedDict[typing.Any, str]"
	target_framework: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
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
			obj, name = unarchiver.decode_values_of_types(b"@", foundation.NSString)
			if obj in self.object_names:
				raise ValueError(f"Duplicate object name entry {i} - this object already has a name")
			
			# Sometimes the name is nil.
			# No idea if this has any special significance
			# or if it behaves any different than having no name entry at all.
			self.object_names[obj] = None if name is None else name.value
		
		self.unknown_set = unarchiver.decode_value_of_type(foundation.NSSet)
		self.connections = unarchiver.decode_value_of_type(foundation.NSArray).elements
		self.unknown_object = unarchiver.decode_value_of_type(b"@")
		
		oids_count = unarchiver.decode_value_of_type(b"i")
		self.object_ids = collections.OrderedDict()
		for i in range(oids_count):
			obj, oid = unarchiver.decode_values_of_types(b"@", b"i")
			if obj in self.object_ids:
				raise ValueError(f"Duplicate object ID entry {i} - this object already has an ID")
			self.object_ids[obj] = oid
		
		self.next_object_id = unarchiver.decode_value_of_type(b"i")
		
		swapper_class_names_count = unarchiver.decode_value_of_type(b"i")
		self.swapper_class_names = collections.OrderedDict()
		for _ in range(swapper_class_names_count):
			obj, class_name = unarchiver.decode_values_of_types(b"@", foundation.NSString)
			self.swapper_class_names[obj] = class_name.value
		
		self.target_framework = unarchiver.decode_value_of_type(foundation.NSString).value
	
	def _oid_repr(self, obj: typing.Any) -> str:
		try:
			oid = self.object_ids[obj]
		except KeyError:
			return "<missing OID!>"
		else:
			return f"#{oid}"
	
	def _object_desc(self, obj: typing.Any) -> str:
		if obj is None:
			return "nil"
		
		desc = _object_class_name(obj)
		
		try:
			name = self.object_names[obj]
		except KeyError:
			pass
		else:
			desc += f" {name!r}"
		
		return f"{self._oid_repr(obj)} ({desc})"
	
	def _render_tree(self, obj: typing.Any, children: typing.Mapping[typing.Any, typing.Any], seen: typing.Set[typing.Any]) -> typing.Iterable[str]:
		yield self._object_desc(obj)
		seen.add(obj)
		for child in children.get(obj, []):
			if child in seen:
				yield f"\tWARNING: object appears more than once in tree: {self._object_desc(obj)}"
			else:
				for line in self._render_tree(child, children, seen):
					yield "\t" + line
	
	def _as_multiline_string_header_(self) -> str:
		return f"{type(self).__name__}, target framework {self.target_framework!r}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		children = collections.defaultdict(list)
		for child, parent in self.object_parents.items():
			children[parent].append(child)
		
		for cs in children.values():
			cs.sort(key=lambda o: self.object_ids.get(o, 0))
		
		seen_in_tree: typing.Set[typing.Any] = set()
		yield from advanced_repr.prefix_lines(
			self._render_tree(self.root, children, seen_in_tree),
			first="object tree: ",
		)
		
		missed_parents = set(children) - seen_in_tree
		if missed_parents:
			yield "WARNING: one or more parent objects not reachable from root:"
			for obj in missed_parents:
				yield f"\t{self._object_desc(obj)} has children:"
				for child in children[obj]:
					yield f"\t\t{self._object_desc(child)}"
		
		missed_names = set(self.object_names) - seen_in_tree
		if missed_names:
			yield "WARNING: one or more named objects not reachable from root:"
			for obj in missed_names:
				yield f"\t{self._object_desc(obj)}"
		
		yield f"{len(self.connections)} connections:"
		for connection in self.connections:
			line = f"\t{self._object_desc(connection)}"
			
			if isinstance(connection, NSIBHelpConnector):
				line += f": {self._object_desc(connection.object)} {connection.key!r} = {connection.value!r}"
			elif isinstance(connection, NSNibConnector):
				source_desc = self._object_desc(connection.source)
				destination_desc = self._object_desc(connection.destination)
				
				if isinstance(connection, NSNibControlConnector):
					line += f": {source_desc} -> [{destination_desc} {connection.label}]"
				elif isinstance(connection, NSNibOutletConnector):
					line += f": {source_desc}.{connection.label} = {destination_desc}"
				else:
					line += f": {source_desc} -> {connection.label!r} -> {destination_desc}"
			
			yield line
		
		missed_objects = set(self.object_ids) - seen_in_tree - set(self.connections)
		if missed_objects:
			yield "WARNING: one or more objects not reachable from root or connections:"
			for obj in missed_objects:
				yield f"\t{self._object_desc(obj)}"
		
		if self.swapper_class_names:
			yield f"{len(self.swapper_class_names)} swapper class names:"
			for obj, class_name in self.swapper_class_names.items():
				yield f"\t{self._object_desc(obj)}: {class_name!r}"
		
		yield f"{len(self.object_ids)} objects:"
		for obj, oid in self.object_ids.items():
			oid_desc = f"#{oid}"
			try:
				name = self.object_names[obj]
			except KeyError:
				pass
			else:
				oid_desc += f" {name!r}"
			
			yield from advanced_repr.prefix_lines(
				advanced_repr.as_multiline_string(obj),
				first=f"\t{oid_desc}: ",
				rest="\t",
			)
		
		yield f"next object ID: #{self.next_object_id}"
		yield from advanced_repr.as_multiline_string(self.unknown_set, prefix="unknown set: ")
		yield from advanced_repr.as_multiline_string(self.unknown_object, prefix="unknown object: ")
	
	def __repr__(self) -> str:
		object_parents_repr = "{" + ", ".join(f"{self._oid_repr(child)}: {self._oid_repr(parent)}" for child, parent in self.object_parents.items()) + "}"
		object_names_repr = "{" + ", ".join(f"{self._oid_repr(obj)}: {name!r}" for obj, name in self.object_names.items()) + "}"
		connections_repr = "[" + ", ".join(f"{self._oid_repr(connection)}" for connection in self.connections) + "]"
		object_ids_repr = "{" + ", ".join(f"<{_object_class_name(obj)}>: {oid}" for obj, oid in self.object_ids.items()) + "}"
		
		return f"<{type(self).__name__}: root={self._oid_repr(self.root)}, object_parents={object_parents_repr}, object_names={object_names_repr}, unknown_set={self.unknown_set!r}, connections={connections_repr}, unknown_object={self.unknown_object!r}, object_ids={object_ids_repr}, next_object_id={self.next_object_id}, target_framework={self.target_framework!r}>"


@archiving.archived_class
class NSIBHelpConnector(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	object: typing.Any
	key: str
	value: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 17:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.object, key, value = unarchiver.decode_values_of_types(b"@", foundation.NSString, foundation.NSString)
		self.key = key.value
		self.value = value.value
	
	def _as_multiline_string_header_(self) -> str:
		return f"{type(self).__name__}, key {self.key!r}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield f"value: {self.value!r}"
		yield from advanced_repr.as_multiline_string(self.object, prefix="object: ")


@archiving.archived_class
class NSNibConnector(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	source: typing.Any
	destination: typing.Any
	label: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 17:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.source, self.destination, label = unarchiver.decode_values_of_types(b"@", b"@", foundation.NSString)
		self.label = label.value
	
	def _as_multiline_string_header_(self) -> str:
		return f"{type(self).__name__}, label {self.label!r}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from advanced_repr.as_multiline_string(self.source, prefix="source: ")
		yield from advanced_repr.as_multiline_string(self.destination, prefix="destination: ")


@archiving.archived_class
class NSNibControlConnector(NSNibConnector):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 207:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_header_(self) -> str:
		return f"{type(self).__name__} <{_object_class_name(self.source)}> -> -[{_object_class_name(self.destination)} {self.label}]"


@archiving.archived_class
class NSNibOutletConnector(NSNibConnector):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 207:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_header_(self) -> str:
		return f"{type(self).__name__} <{_object_class_name(self.source)}>.{self.label} = <{_object_class_name(self.destination)}>"


class NSControlStateValue(enum.Enum):
	mixed = -1
	off = 0
	on = 1


class NSEventModifierFlags(enum.IntFlag):
	caps_lock = 1 << 16
	shift = 1 << 17
	control = 1 << 18
	option = 1 << 19
	command = 1 << 20
	numeric_pad = 1 << 21
	help = 1 << 22
	function = 1 << 23
	
	device_independent_flags_mask = 0xffff0000
	
	def __str__(self) -> str:
		if self == 0:
			return "(no modifiers)"
		
		flags = self
		modifiers = []
		
		for flag, name in _MODIFIER_KEY_NAMES.items():
			if flag in flags:
				modifiers.append(name)
				flags &= ~flag
		
		if flags:
			# Render any remaining unknown flags as plain hex.
			modifiers.append(f"({flags:#x})")
		
		return "+".join(modifiers)


_MODIFIER_KEY_NAMES = collections.OrderedDict([
	(NSEventModifierFlags.caps_lock, "CapsLock"),
	(NSEventModifierFlags.shift, "Shift"),
	(NSEventModifierFlags.control, "Ctrl"),
	(NSEventModifierFlags.option, "Alt"),
	(NSEventModifierFlags.command, "Cmd"),
	(NSEventModifierFlags.numeric_pad, "(NumPad)"),
	(NSEventModifierFlags.help, "(Help)"),
	(NSEventModifierFlags.function, "(FKey)"),
])


@archiving.archived_class
class NSMenuItem(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	menu: "NSMenu"
	flags: int
	title: str
	key_equivalent: str
	modifier_flags: NSEventModifierFlags
	state: NSControlStateValue
	on_state_image: typing.Any
	off_state_image: typing.Any
	mixed_state_image: typing.Any
	action: stream.Selector
	int_2: int
	target: typing.Any
	submenu: "typing.Optional[NSMenu]"
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version not in {505, 671}:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.menu = unarchiver.decode_value_of_type(NSMenu)
		(
			flags, title, key_equivalent, modifier_flags,
			int_1, state,
			obj_1, self.on_state_image, self.off_state_image, self.mixed_state_image,
			self.action, self.int_2, obj_2,
		) = unarchiver.decode_values_of_types(
			b"i", foundation.NSString, foundation.NSString, b"I",
			b"I", b"i",
			b"@", b"@", b"@", b"@",
			b":", b"i", b"@",
		)
		
		self.flags = flags & 0xffffffff
		self.title = title.value
		self.key_equivalent = key_equivalent.value
		self.modifier_flags = NSEventModifierFlags(modifier_flags)
		self.state = NSControlStateValue(state)
		
		if int_1 != 0x7fffffff:
			raise ValueError(f"Unknown int 1 is not 0x7fffffff: {int_1}")
		if obj_1 is not None:
			raise ValueError("Unknown object 1 is not nil")
		if obj_2 is not None:
			raise ValueError("Unknown object 2 is not nil")
		
		self.target = unarchiver.decode_value_of_type(b"@")
		self.submenu = unarchiver.decode_value_of_type(NSMenu)
	
	def _as_multiline_string_header_(self) -> str:
		header = f"{type(self).__name__} {self.title!r}"
		if self.key_equivalent:
			header += f" ({self.modifier_flags!s}+{self.key_equivalent!r})"
		return header
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield f"in menu: <{_object_class_name(self.menu)} {self.menu.title!r}>"
		
		if self.flags != 0:
			yield f"flags: 0x{self.flags:>08x}"
		
		if self.state != NSControlStateValue.off:
			yield f"initial state: {self.state.name}"
		
		if not isinstance(self.on_state_image, NSCustomResource) or self.on_state_image.class_name != "NSImage" or self.on_state_image.resource_name != "NSMenuCheckmark":
			yield from advanced_repr.as_multiline_string(self.on_state_image, prefix="on state image: ")
		
		if self.off_state_image is not None:
			yield from advanced_repr.as_multiline_string(self.off_state_image, prefix="off state image: ")
		
		if not isinstance(self.mixed_state_image, NSCustomResource) or self.mixed_state_image.class_name != "NSImage" or self.mixed_state_image.resource_name != "NSMenuMixedState":
			yield from advanced_repr.as_multiline_string(self.mixed_state_image, prefix="mixed state image: ")
		
		if self.action is not None:
			yield f"action: {self.action}"
		if self.int_2 != 0:
			yield f"unknown int 2: {self.int_2}"
		if self.target is not None:
			yield f"target: <{_object_class_name(self.target)}>"
		
		if self.submenu is not None:
			yield from advanced_repr.as_multiline_string(self.submenu, prefix="submenu: ")


@archiving.archived_class
class NSMenu(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	title: str
	items: typing.List[NSMenuItem]
	identifier: typing.Optional[str]
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 204:
			raise ValueError(f"Unsupported version: {class_version}")
		
		unknown_int, title, items, identifier = unarchiver.decode_values_of_types(b"i", foundation.NSString, foundation.NSArray, foundation.NSString)
		
		if unknown_int != 0:
			raise ValueError(f"Unknown int is not 0: {unknown_int}")
		
		self.title = title.value
		
		self.items = []
		for item in items.elements:
			if not isinstance(item, NSMenuItem):
				raise TypeError(f"NSMenu items must be instances of NSMenuItem, not {type(item).__name__}")
			
			self.items.append(item)
		
		if identifier is None:
			self.identifier = None
		else:
			self.identifier = identifier.value
	
	def _as_multiline_string_header_(self) -> str:
		header = f"{type(self).__name__} {self.title!r}"
		
		if self.identifier is not None:
			header += f" ({self.identifier!r})"
		
		if not self.items:
			header += ", no items"
		elif len(self.items) == 1:
			header += ", 1 item"
		else:
			header += f", {len(self.items)} items"
		
		return header
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for item in self.items:
			yield from advanced_repr.as_multiline_string(item)


@archiving.archived_class
class NSCell(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	flags_unknown: typing.Tuple[int, int]
	title_or_image: typing.Any
	font: NSFont
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 65:
			raise ValueError(f"Unsupported version: {class_version}")
		
		flags_1, flags_2 = unarchiver.decode_values_of_types(b"i", b"i")
		self.flags_unknown = (flags_1 & 0xffffffff, flags_2 & 0xffffffff)
		
		self.title_or_image, self.font, obj_3, obj_4 = unarchiver.decode_values_of_types(b"@", NSFont, b"@", b"@")
		if obj_3 is not None:
			raise ValueError("Unknown object 3 is not nil")
		if obj_4 is not None:
			raise ValueError("Unknown object 4 is not nil")
	
	def _as_multiline_string_header_(self) -> str:
		return type(self).__name__
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield f"flags: (0x{self.flags_unknown[0]:>08x}, 0x{self.flags_unknown[1]:>08x})"
		yield f"title/image: {self.title_or_image!r}"
		yield f"font: {self.font!r}"


class NSImageAlignment(enum.Enum):
	center = 0
	top = 1
	top_left = 2
	top_right = 3
	left = 4
	bottom = 5
	bottom_left = 6
	bottom_right = 7
	right = 8


class NSImageFrameStyle(enum.Enum):
	none = 0
	photo = 1
	gray_bezel = 2
	groove = 3
	button = 4


class NSImageScaling(enum.Enum):
	proportionally_down = 0
	axes_independently = 1
	none = 2
	proportionally_up_or_down = 3


@archiving.archived_class
class NSImageCell(NSCell):
	image_alignment: NSImageAlignment
	image_scaling: NSImageScaling
	image_frame_style: NSImageFrameStyle
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsupported version: {class_version}")
		
		image_alignment, image_scaling, image_frame_style = unarchiver.decode_values_of_types(b"i", b"i", b"i")
		self.image_alignment = NSImageAlignment(image_alignment)
		self.image_scaling = NSImageScaling(image_scaling)
		self.image_frame_style = NSImageFrameStyle(image_frame_style)
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"image alignment: {self.image_alignment.name}"
		yield f"image scaling: {self.image_scaling.name}"
		yield f"image frame style: {self.image_frame_style.name}"


@archiving.archived_class
class NSActionCell(NSCell):
	tag: int
	action: typing.Optional[stream.Selector]
	target: typing.Any
	control_view: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 17:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.tag, self.action = unarchiver.decode_values_of_types(b"i", b":")
		
		self.target = unarchiver.decode_value_of_type(b"@")
		
		self.control_view = unarchiver.decode_value_of_type(b"@")
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		if self.tag != 0:
			yield f"tag: {self.tag}"
		
		if self.action is not None:
			yield f"action: {self.action!r}"
		
		if self.target is not None:
			yield f"target: <{_object_class_name(self.target)}>"
		
		if self.control_view is None:
			control_view_desc = "None"
		else:
			control_view_desc = f"<{_object_class_name(self.control_view)}>"
		yield f"control view: {control_view_desc}"


class NSButtonType(enum.Enum):
	momentary_light = 0
	push_on_push_off = 1
	toggle = 2
	switch = 3
	radio = 4
	momentary_change = 5
	on_off = 6
	momentary_push_in = 7
	accelerator = 8
	multi_level_accelerator = 9


@archiving.archived_class
class NSButtonImageSource(foundation.NSObject):
	resource_name: str
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 3:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.resource_name = unarchiver.decode_value_of_type(foundation.NSString).value
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(resource_name={self.resource_name!r})"


@archiving.archived_class
class NSButtonCell(NSActionCell):
	shorts_unknown: typing.Tuple[int, int]
	type: NSButtonType
	type_flags: int
	flags: int
	key_equivalent: str
	image_1: typing.Any
	image_2_or_font: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 63:
			raise ValueError(f"Unsupported version: {class_version}")
		
		(
			short_1, short_2, button_type, flags,
			string_1, key_equivalent, self.image_1, self.image_2_or_font, unknown_object,
		) = unarchiver.decode_values_of_types(
			b"s", b"s", b"i", b"i",
			foundation.NSString, foundation.NSString, b"@", b"@", b"@",
		)
		
		self.shorts_unknown = (short_1, short_2)
		if self.shorts_unknown not in {(200, 25), (400, 75)}:
			raise ValueError(f"Unexpected value for unknown shorts: {self.shorts_unknown}")
		
		self.type = NSButtonType(button_type & 0xffffff)
		self.type_flags = button_type & 0xff000000
		self.flags = flags & 0xffffffff
		
		if string_1 is not None and string_1.value:
			raise ValueError(f"Unknown string 1 is not nil or empty: {string_1}")
		
		self.key_equivalent = key_equivalent.value
		
		if unknown_object is not None:
			raise ValueError("Unknown object is not nil")
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"unknown shorts: {self.shorts_unknown!r}"
		yield f"button type: {self.type.name}"
		if self.type_flags != 0:
			yield f"button type flags: 0x{self.type_flags:>08x}"
		yield f"button flags: 0x{self.flags:>08x}"
		
		if self.key_equivalent:
			yield f"key equivalent: {self.key_equivalent!r}"
		if self.image_1 is not None:
			yield from advanced_repr.as_multiline_string(self.image_1, prefix="image 1: ")
		if self.image_2_or_font is not None:
			yield from advanced_repr.as_multiline_string(self.image_2_or_font, prefix="image 2 or font: ")


@archiving.archived_class
class NSTextFieldCell(NSActionCell):
	draws_background: bool
	background_color: NSColor
	text_color: NSColor
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version not in {61, 62}:
			raise ValueError(f"Unsupported version: {class_version}")
		
		draws_background, self.background_color, self.text_color = unarchiver.decode_values_of_types(b"c", NSColor, NSColor)
		
		if draws_background == 0:
			self.draws_background = False
		elif draws_background == 1:
			self.draws_background = True
		else:
			raise ValueError(f"Unexpected value for boolean: {draws_background}")
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"draws background: {self.draws_background}"
		yield f"background color: {self.background_color}"
		yield f"text color: {self.text_color}"


@archiving.archived_class
class NSComboBoxCell(NSTextFieldCell):
	number_of_visible_items: int
	values: typing.List[typing.Any]
	combo_box: "NSView"
	button_cell: NSButtonCell
	table_view: "NSView"
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 2:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.number_of_visible_items, bool_1, bool_2, bool_3 = unarchiver.decode_values_of_types(b"i", b"c", b"c", b"c")
		
		if bool_1 != 1:
			raise ValueError(f"Unknown boolean 1 is not 1: {bool_1}")
		if bool_2 != 1:
			raise ValueError(f"Unknown boolean 2 is not 1: {bool_2}")
		if bool_3 != 0:
			raise ValueError(f"Unknown boolean 3 is not 0: {bool_3}")
		
		self.values = unarchiver.decode_value_of_type(foundation.NSArray).elements
		
		unknown_object = unarchiver.decode_value_of_type(b"@")
		if unknown_object is not None:
			raise ValueError("Unknown object is not nil")
		
		self.combo_box = unarchiver.decode_value_of_type(NSView)
		self.button_cell = unarchiver.decode_value_of_type(NSButtonCell)
		self.table_view = unarchiver.decode_value_of_type(NSView)
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"number of visible items: {self.number_of_visible_items}"
		
		if self.values:
			if len(self.values) == 1:
				yield "1 value:"
			else:
				yield f"{len(self.values)} values:"
			
			for value in self.values:
				for line in advanced_repr.as_multiline_string(value):
					yield "\t" + line
		
		yield f"combo box: <{_object_class_name(self.combo_box)}>"
		yield from advanced_repr.as_multiline_string(self.button_cell, prefix="button cell: ")
		yield from advanced_repr.as_multiline_string(self.table_view, prefix="table view: ")


@archiving.archived_class
class NSTableHeaderCell(NSTextFieldCell):
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 28:
			raise ValueError(f"Unsupported version: {class_version}")


@archiving.archived_class
class NSResponder(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	next_responder: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.next_responder = unarchiver.decode_value_of_type(b"@")
	
	def _as_multiline_string_header_(self) -> str:
		return type(self).__name__
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		if self.next_responder is None:
			next_responder_desc = "None"
		else:
			next_responder_desc = f"<{_object_class_name(self.next_responder)}>"
		yield f"next responder: {next_responder_desc}"
	
	def __repr__(self) -> str:
		if self.next_responder is None:
			next_responder_desc = "None"
		else:
			next_responder_desc = f"<{_object_class_name(self.next_responder)}>"
		return f"{type(self).__name__}(next_responder={next_responder_desc})"


@archiving.archived_class
class NSView(NSResponder):
	flags: int
	subviews: typing.List[typing.Any]
	registered_dragged_types: typing.List[str]
	frame: foundation.NSRect
	bounds: foundation.NSRect
	superview: typing.Any
	content_view: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.flags = unarchiver.decode_value_of_type(b"i")
		
		(
			subviews, obj2, obj3, registered_dragged_types,
			frame_x, frame_y, frame_width, frame_height,
			bounds_x, bounds_y, bounds_width, bounds_height,
		) = unarchiver.decode_values_of_types(
			foundation.NSArray, b"@", b"@", foundation.NSSet,
			b"f", b"f", b"f", b"f",
			b"f", b"f", b"f", b"f",
		)
		
		if subviews is None:
			self.subviews = []
		else:
			self.subviews = subviews.elements
		
		if obj2 is not None:
			raise ValueError("Unknown object 2 is not nil")
		if obj3 is not None:
			raise ValueError("Unknown object 3 is not nil")
		
		self.registered_dragged_types = []
		if registered_dragged_types is not None:
			for tp in registered_dragged_types.elements:
				if not isinstance(tp, foundation.NSString):
					raise TypeError(f"NSView dragged types must be instances of NSString, not {type(tp).__name__}")
				
				self.registered_dragged_types.append(tp.value)
		
		self.frame = foundation.NSRect.make(frame_x, frame_y, frame_width, frame_height)
		self.bounds = foundation.NSRect.make(bounds_x, bounds_y, bounds_width, bounds_height)
		
		self.superview = unarchiver.decode_value_of_type(b"@")
		
		obj6 = unarchiver.decode_value_of_type(b"@")
		if obj6 is not None:
			raise ValueError("Unknown object 6 is not nil")
		self.content_view = unarchiver.decode_value_of_type(b"@")
		obj8 = unarchiver.decode_value_of_type(b"@")
		if obj8 is not None:
			raise ValueError("Unknown object 8 is not nil")
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"flags: 0x{self.flags:>08x}"
		
		if self.subviews:
			yield f"{len(self.subviews)} {'subview' if len(self.subviews) == 1 else 'subviews'}:"
			for subview in self.subviews:
				for line in advanced_repr.as_multiline_string(subview):
					yield "\t" + line
		
		if self.registered_dragged_types:
			yield f"{len(self.registered_dragged_types)} registered dragged types:"
			for tp in self.registered_dragged_types:
				yield f"\t{tp!r}"
		
		yield f"frame: {self.frame}"
		yield f"bounds: {self.bounds}"
		
		if self.superview is None:
			superview_desc = "None"
		else:
			superview_desc = f"<{_object_class_name(self.superview)}>"
		yield f"superview: {superview_desc}"
		
		if self.content_view is not None:
			yield f"content view: <{_object_class_name(self.content_view)}>"


@archiving.archived_class
class NSControl(NSView):
	int_1: int
	bool_1: bool
	cell: typing.Optional[NSCell]
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 41:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.int_1, bool_1, int_3, self.cell = unarchiver.decode_values_of_types(b"i", b"c", b"c", NSCell)
		
		if bool_1 == 0:
			self.bool_1 = False
		elif bool_1 == 1:
			self.bool_1 = True
		else:
			raise ValueError(f"Unexpected value for boolean: {bool_1}")
		
		if int_3 != 0:
			raise ValueError(f"Unknown int 3 is not 0: {int_3}")
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		yield f"unknown int 1: {self.int_1}"
		yield f"unknown boolean 1: {self.bool_1}"
		yield from advanced_repr.as_multiline_string(self.cell, prefix="cell: ")

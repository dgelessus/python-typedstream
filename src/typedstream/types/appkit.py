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
from . import _common
from . import foundation


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
		it = iter(advanced_repr.as_multiline_string(self.object))
		yield f"{type(self).__name__}, class {self.class_name}, object: " + next(it, "")
		for line in it:
			yield "\t" + line
	
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
		
		unknown_int = unarchiver.decode_value_of_type(b"i")
		if unknown_int != 0:
			raise ValueError(f"Unknown int field is not 0: {unknown_int}")
		
		self.target_framework = unarchiver.decode_value_of_type(foundation.NSString).value
	
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
		tree_it = iter(self._render_tree(self.root, children, seen_in_tree))
		yield f"object tree: {next(tree_it)}"
		yield from tree_it
		
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
			yield f"\t{self._object_desc(connection)}"
		
		missed_objects = set(self.object_ids) - seen_in_tree - set(self.connections)
		if missed_objects:
			yield "WARNING: one or more objects not reachable from root or connections:"
			for obj in missed_objects:
				yield f"\t{self._object_desc(obj)}"
		
		yield f"{len(self.object_ids)} objects:"
		for obj, oid in self.object_ids.items():
			oid_desc = f"#{oid}"
			try:
				name = self.object_names[obj]
			except KeyError:
				pass
			else:
				oid_desc += f" {name!r}"
			
			obj_it = iter(advanced_repr.as_multiline_string(obj))
			yield f"\t{oid_desc}: {next(obj_it)}"
			for line in obj_it:
				yield "\t" + line
		
		yield f"next object ID: #{self.next_object_id}"
		
		unknown_set_it = iter(advanced_repr.as_multiline_string(self.unknown_set))
		yield f"unknown set: {next(unknown_set_it)}"
		yield from unknown_set_it
		
		unknown_object_it = iter(advanced_repr.as_multiline_string(self.unknown_object))
		yield f"unknown object: {next(unknown_object_it)}"
		yield from unknown_object_it
	
	def __repr__(self) -> str:
		object_parents_repr = "{" + ", ".join(f"{self._oid_repr(child)}: {self._oid_repr(parent)}" for child, parent in self.object_parents.items()) + "}"
		object_names_repr = "{" + ", ".join(f"{self._oid_repr(obj)}: {name!r}" for obj, name in self.object_names.items()) + "}"
		connections_repr = "[" + ", ".join(f"{self._oid_repr(connection)}" for connection in self.connections) + "]"
		object_ids_repr = "{" + ", ".join(f"<{_common.object_class_name(obj)}>: {oid}" for obj, oid in self.object_ids.items()) + "}"
		
		return f"<{type(self).__name__}: root={self._oid_repr(self.root)}, object_parents={object_parents_repr}, object_names={object_names_repr}, unknown_set={self.unknown_set!r}, connections={connections_repr}, unknown_object={self.unknown_object!r}, object_ids={object_ids_repr}, next_object_id={self.next_object_id}, target_framework={self.target_framework!r}>"


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


@archiving.archived_class
class NSActionCell(NSCell):
	action: typing.Optional[stream.Selector]
	target: typing.Any
	control_view: "typing.Optional[NSView]"
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 17:
			raise ValueError(f"Unsupported version: {class_version}")
		
		unknown_int, self.action = unarchiver.decode_values_of_types(b"i", b":")
		if unknown_int != 0:
			raise ValueError(f"Unknown integer is not 0: {unknown_int}")
		
		self.target = unarchiver.decode_value_of_type(b"@")
		
		self.control_view = unarchiver.decode_value_of_type(NSView)
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		yield from super()._as_multiline_string_body_()
		
		if self.action is not None:
			yield f"action: {self.action!r}"
		
		if self.target is not None:
			yield f"target: <{_common.object_class_name(self.target)}>"
		
		if self.control_view is None:
			control_view_desc = "None"
		else:
			control_view_desc = f"<{_common.object_class_name(self.control_view)}>"
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
	shorts_unknown = typing.Tuple[int, int]
	type: NSButtonType
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
		
		self.type = NSButtonType(button_type)
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
		yield f"button flags: 0x{self.flags:>08x}"
		
		if self.key_equivalent:
			yield f"key equivalent: {self.key_equivalent!r}"
		if self.image_1 is not None:
			image_1_it = iter(advanced_repr.as_multiline_string(self.image_1))
			yield f"image 1: {next(image_1_it)}"
			yield from image_1_it
		if self.image_2_or_font is not None:
			image_2_it = iter(advanced_repr.as_multiline_string(self.image_2_or_font))
			yield f"image 2 or font: {next(image_2_it)}"
			yield from image_2_it


@archiving.archived_class
class NSTextFieldCell(NSActionCell):
	draws_background: bool
	background_color: NSColor
	text_color: NSColor
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 62:
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
		
		yield f"combo box: <{_common.object_class_name(self.combo_box)}>"
		
		button_cell_it = iter(advanced_repr.as_multiline_string(self.button_cell))
		yield f"button cell: {next(button_cell_it)}"
		yield from button_cell_it
		
		table_view_it = iter(advanced_repr.as_multiline_string(self.table_view))
		yield f"table view: {next(table_view_it)}"
		yield from table_view_it


@archiving.archived_class
class NSResponder(foundation.NSObject, advanced_repr.AsMultilineStringBase):
	next_responder: typing.Any
	
	def _init_from_unarchiver_(self, unarchiver: archiving.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")
		
		self.next_responder = unarchiver.decode_value_of_type(NSResponder)
	
	def _as_multiline_string_header_(self) -> str:
		return type(self).__name__
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		if self.next_responder is None:
			next_responder_desc = "None"
		else:
			next_responder_desc = f"<{_common.object_class_name(self.next_responder)}>"
		yield f"next responder: {next_responder_desc}"
	
	def __repr__(self) -> str:
		if self.next_responder is None:
			next_responder_desc = "None"
		else:
			next_responder_desc = f"<{_common.object_class_name(self.next_responder)}>"
		return f"{type(self).__name__}(next_responder={next_responder_desc})"


@archiving.archived_class
class NSView(NSResponder):
	flags: int
	subviews: "typing.List[NSView]"
	registered_dragged_types: typing.List[str]
	frame: foundation.NSRect
	bounds: foundation.NSRect
	superview: "typing.Optional[NSView]"
	content_view: "NSView"
	
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
		
		self.subviews = []
		if subviews is not None:
			for subview in subviews.elements:
				if not isinstance(subview, NSView):
					raise TypeError(f"NSView subviews must be instances of NSView, not {type(subview).__name__}")
				
				self.subviews.append(subview)
		
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
		
		self.frame = foundation.NSRect(foundation.NSPoint(frame_x, frame_y), foundation.NSSize(frame_width, frame_height))
		self.bounds = foundation.NSRect(foundation.NSPoint(bounds_x, bounds_y), foundation.NSSize(bounds_width, bounds_height))
		
		self.superview = unarchiver.decode_value_of_type(NSView)
		
		obj6 = unarchiver.decode_value_of_type(b"@")
		if obj6 is not None:
			raise ValueError("Unknown object 6 is not nil")
		self.content_view = unarchiver.decode_value_of_type(NSView)
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
			superview_desc = f"<{_common.object_class_name(self.superview)}>"
		yield f"superview: {superview_desc}"
		
		if self.content_view is not None:
			yield f"content view: <{_common.object_class_name(self.content_view)}>"

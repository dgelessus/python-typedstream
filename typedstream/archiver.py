import typing

from . import advanced_repr
from . import stream


class Group(tuple, advanced_repr.AsMultilineStringBase):
	"""Representation of a group of values packed together in a typedstream.
	
	This is a slightly modified version of the standard ``tuple`` type that adds a multiline string representation.
	
	Value groups in a typedstream are created by serializing multiple values with a single call to ``-[NSArchiver encodeValuesOfObjCTypes:]``.
	This produces different serialized data than calling ``-[NSArchiver encodeValueOfObjCType:at:]`` separately for each of the values.
	The former serializes all values' type encodings joined together into a single string,
	followed by all of the values one immediately after another.
	The latter serializes each value as a separate encoding/value pair.
	
	A :class:`Group` instance returned by :class:`Unarchiver` always contains at least two values.
	Single values are returned directly and not wrapped in a :class:`Group` object.
	Empty groups are technically supported by the typedstream format,
	but :class:`Unarchiver` treats them as an error,
	as they are never used in practice.
	"""
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		yield "group:"
		for value in self:
			for line in advanced_repr.as_multiline_string(value, calling_self=self, state=state):
				yield "\t" + line


class Class(object):
	"""Information about a class as it is stored at the start of objects in a typedstream."""
	
	name: bytes
	version: int
	superclass: typing.Optional["Class"]
	
	def __init__(self, name: bytes, version: int, superclass: typing.Optional["Class"]) -> None:
		super().__init__()
		
		self.name = name
		self.version = version
		self.superclass = superclass
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, version={self.version!r}, superclass={self.superclass!r})"
	
	def __str__(self) -> str:
		rep = f"{self.name.decode('ascii', errors='backslashreplace')} v{self.version}"
		
		if self.superclass is not None:
			rep += f", extends {self.superclass}"
		
		return rep


class Object(advanced_repr.AsMultilineStringBase):
	"""Representation of an object as it is stored in a typedstream."""
	
	clazz: Class
	contents: typing.List[typing.Any]
	
	def __init__(self, clazz: Class, contents: typing.List[typing.Any]) -> None:
		super().__init__()
		
		self.clazz = clazz
		self.contents = contents
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(clazz={self.clazz!r}, contents={self.contents!r})"
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		first = f"object of class {self.clazz}"
		if id(self) in state.currently_rendering_ids:
			yield first + " (circular reference)"
		elif id(self) in state.already_rendered_ids:
			yield first + " (backreference)"
		elif not self.contents:
			yield first + ", no contents"
		else:
			yield first + ", contents:"
			for value in self.contents:
				for line in advanced_repr.as_multiline_string(value, calling_self=self, state=state):
					yield "\t" + line


class Struct(advanced_repr.AsMultilineStringBase):
	"""Representation of a C struct as it is stored in a typedstream."""
	
	fields: typing.List[typing.Any]
	
	def __init__(self, fields: typing.List[typing.Any]) -> None:
		super().__init__()
		
		self.fields = fields
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(fields={self.fields!r})"
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		yield "struct:"
		for field_value in self.fields:
			for line in advanced_repr.as_multiline_string(field_value, calling_self=self, state=state):
				yield "\t" + line


# Placeholder for unset lookahead parameters.
# Cannot use None for this,
# because None is a valid event.
_NO_LOOKAHEAD = object()


class Unarchiver(object):
	reader: stream.TypedStreamReader
	_lookahead: typing.Any
	shared_object_table: typing.List[typing.Tuple[stream.ObjectReference.Type, typing.Any]]
	
	def __init__(self, reader: stream.TypedStreamReader) -> None:
		super().__init__()
		
		self.reader = reader
		self.shared_object_table = []
	
	def _lookup_reference(self, ref: stream.ObjectReference) -> typing.Any:
		ref_type, obj = self.shared_object_table[ref.number]
		if ref.referenced_type != ref_type:
			raise ValueError(f"Object reference type mismatch: reference should point to an object of type {ref.referenced_type.value}, but the referenced object number {ref.number} has type {ref_type.value}")
		return obj
	
	def decode_any_untyped_value(self) -> typing.Any:
		first = next(self.reader)
		
		if first is None or isinstance(first, (int, float, bytes)):
			return first
		elif isinstance(first, stream.ObjectReference):
			return self._lookup_reference(first)
		elif isinstance(first, stream.CString):
			self.shared_object_table.append((stream.ObjectReference.Type.C_STRING, first.contents))
			return first.contents
		elif isinstance(first, stream.Selector):
			return first.name
		elif isinstance(first, stream.SingleClass):
			# Read the superclass chain until (and including) the terminating Nil or reference.
			single_classes = [first]
			next_class_event = next(self.reader)
			while next_class_event is not None and not isinstance(next_class_event, stream.ObjectReference):
				if not isinstance(next_class_event, stream.SingleClass):
					raise ValueError(f"Expected SingleClass, ObjectReference, or None, not {type(next_class_event)}")
				single_classes.append(next_class_event)
				next_class_event = next(self.reader)
			
			# Resolve the possibly Nil superclass of the last literally stored class.
			terminating_event = next_class_event
			if terminating_event is None:
				next_superclass = None
			elif isinstance(terminating_event, stream.ObjectReference):
				next_superclass = self._lookup_reference(terminating_event)
			else:
				raise AssertionError()
			
			# Convert the SingleClass events from the stream into Class objects with a superclass.
			# (The terminating Nil or reference is not included in this list,
			# so that it doesn't get an object number assigned.)
			# This list is built up backwards,
			# because of how the SingleClass objects are stored in the stream -
			# each class is stored *before* its superclass,
			# but each Class object can only be constructed *after* its superclass Class has been constructed/looked up.
			# So we iterate over the SingleClass events in reverse order,
			# and store the Class objects in reverse order of construction,
			# so that in the end new_classes matches the order stored in the stream.
			new_classes: typing.List[Class] = []
			for single_class in reversed(single_classes):
				next_superclass = Class(single_class.name, single_class.version, next_superclass)
				new_classes.insert(0, next_superclass)
			
			# Object numbers for classes are assigned in the same order as they are stored in the stream.
			for new_class in new_classes:
				self.shared_object_table.append((stream.ObjectReference.Type.CLASS, new_class))
			
			return next_superclass
		elif isinstance(first, stream.BeginObject):
			# The object's number is assigned *before* its class information is read,
			# but at this point we can't create the object yet
			# (because we don't know its class),
			# so insert a placeholder value for now.
			# This placeholder value is only used to make object number assignments happen in the right order.
			# It's never used when actually looking up a reference,
			# because it's replaced immediately after the class information is fully read,
			# and the class information can only contain references to other classes and not objects.
			placeholder_index = len(self.shared_object_table)
			self.shared_object_table.append((stream.ObjectReference.Type.OBJECT, None))
			
			obj_class = self.decode_any_untyped_value()
			if not isinstance(obj_class, Class):
				raise ValueError(f"Object class must be a Class, not {type(obj_class)}")
			
			# Now that the class is known,
			# we can create the actual object,
			# and replace the placeholder in the shared object table.
			obj = Object(obj_class, [])
			self.shared_object_table[placeholder_index] = (stream.ObjectReference.Type.OBJECT, obj)
			
			next_event = next(self.reader)
			while not isinstance(next_event, stream.EndObject):
				obj.contents.append(self.decode_typed_values(_lookahead=next_event))
				next_event = next(self.reader)
			
			return obj
		elif isinstance(first, stream.ByteArray):
			return first.data
		elif isinstance(first, stream.BeginArray):
			array = [self.decode_any_untyped_value() for _ in range(first.length)]
			
			end = next(self.reader)
			if not isinstance(end, stream.EndArray):
				raise ValueError(f"Expected EndArray, not {type(end)}")
			
			return array
		elif isinstance(first, stream.BeginStruct):
			fields = [self.decode_any_untyped_value() for _ in first.field_encodings]
			
			end = next(self.reader)
			if not isinstance(end, stream.EndStruct):
				raise ValueError(f"Expected EndStruct, not {type(end)}")
			
			return Struct(fields)
		else:
			raise ValueError(f"Unexpected event at beginning of untyped value: {type(first)}")
	
	def decode_typed_values(self, *, _lookahead: typing.Any = _NO_LOOKAHEAD) -> typing.Any:
		if _lookahead is _NO_LOOKAHEAD:
			begin = next(self.reader)
		else:
			begin = _lookahead
		
		if not isinstance(begin, stream.BeginTypedValues):
			raise ValueError(f"Expected BeginTypedValues, not {type(begin)}")
		
		if len(begin.encodings) == 1:
			# Single typed values are quite common,
			# so for convenience don't wrap them in a 1-element tuple.
			ret = self.decode_any_untyped_value()
		else:
			ret = Group(self.decode_any_untyped_value() for _ in begin.encodings)
		
		end = next(self.reader)
		if not isinstance(end, stream.EndTypedValues):
			raise ValueError(f"Expected EndTypedValues, not {type(end)}")
		
		return ret
	
	def decode_all(self) -> typing.Sequence[typing.Any]:
		contents = []
		
		while True:
			try:
				lookahead = next(self.reader)
			except StopIteration:
				break
			
			contents.append(self.decode_typed_values(_lookahead=lookahead))
		
		return contents

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


import abc
import os
import types
import typing

from . import advanced_repr
from . import encodings
from . import old_binary_plist
from . import stream


__all__ = [
	"TypedGroup",
	"TypedValue",
	"Class",
	"GenericArchivedObject",
	"KnownArchivedObject",
	"archived_classes_by_name",
	"register_archived_class",
	"archived_class",
	"lookup_archived_class",
	"instantiate_archived_class",
	"GenericStruct",
	"KnownStruct",
	"struct_classes_by_encoding",
	"register_struct_class",
	"struct_class",
	"Unarchiver",
	"unarchive_from_stream",
	"unarchive_from_data",
	"unarchive_from_file",
]


class TypedGroup(advanced_repr.AsMultilineStringBase):
	"""Representation of a group of typed values packed together in a typedstream.
	
	Value groups in a typedstream are created by serializing multiple values with a single call to ``-[NSArchiver encodeValuesOfObjCTypes:]``.
	This produces different serialized data than calling ``-[NSArchiver encodeValueOfObjCType:at:]`` separately for each of the values.
	The former serializes all values' type encodings joined together into a single string,
	followed by all of the values one immediately after another.
	The latter serializes each value as a separate encoding/value pair.
	
	A :class:`TypedGroup` instance returned by :class:`Unarchiver` always contains at least one value
	(groups with exactly one value are represented using the subclass :class:`TypedValue` instead).
	Empty groups are technically supported by the typedstream format,
	but :class:`Unarchiver` treats them as an error,
	as they are never used in practice.
	"""
	
	detect_backreferences = False
	
	encodings: typing.Sequence[bytes]
	values: typing.Sequence[typing.Any]
	
	def __init__(self, encodings: typing.Sequence[bytes], values: typing.Sequence[typing.Any]) -> None:
		super().__init__()
		
		self.encodings = encodings
		self.values = values
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(encodings={self.encodings!r}, values={self.values!r})"
	
	def _as_multiline_string_header_(self) -> str:
		return "group"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for encoding, value in zip(self.encodings, self.values):
			yield from advanced_repr.as_multiline_string(value, prefix=f"type {encoding!r}: ")


class TypedValue(TypedGroup):
	"""Special case of :class:`TypedGroup` for groups that contain only a single value.
	
	This class provides convenient properties for accessing the group's single type encoding and value,
	as well as cleaner string representations.
	Single-value groups are very common,
	so this improves usability and readability in many cases.
	"""
	
	@property
	def encoding(self) -> bytes:
		return self.encodings[0]
	
	@property
	def value(self) -> typing.Any:
		return self.values[0]
	
	def __init__(self, encoding: bytes, value: typing.Any) -> None:
		super().__init__([encoding], [value])
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(encoding={self.encoding!r}, value={self.value!r})"
	
	def _as_multiline_string_(self) -> typing.Iterable[str]:
		yield from advanced_repr.as_multiline_string(self.value, prefix=f"type {self.encoding!r}: ")


class Array(advanced_repr.AsMultilineStringBase):
	"""Representation of a primitive C array stored in a typedstream."""
	
	detect_backreferences = False
	
	elements: typing.Sequence[typing.Any]
	
	def __init__(self, elements: typing.Sequence[typing.Any]) -> None:
		super().__init__()
		
		self.elements = elements
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.elements!r})"
	
	def _as_multiline_string_header_(self) -> str:
		if isinstance(self.elements, bytes):
			return f"array, {len(self.elements)} bytes: {self.elements!r}"
		else:
			return f"array, {len(self.elements)} elements"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		if not isinstance(self.elements, bytes): # Byte arrays are displayed entirely in the header
			for element in self.elements:
				yield from advanced_repr.as_multiline_string(element)


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


class GenericArchivedObject(advanced_repr.AsMultilineStringBase):
	"""Representation of a generic object as it is stored in a typedstream.
	
	This class is only used for archived objects whose class is not known.
	Objects of known classes are represented as instances of custom Python classes instead.
	If an object's class is not known,
	but one of its superclasses is,
	then the known part of the object is represented as that known class
	and only the remaining contents are stored in the generic format.
	"""
	
	clazz: Class
	super_object: "typing.Optional[KnownArchivedObject]"
	contents: typing.List[TypedGroup]
	
	def __init__(self, clazz: Class, super_object: "typing.Optional[KnownArchivedObject]", contents: typing.List[TypedGroup]) -> None:
		super().__init__()
		
		self.clazz = clazz
		self.super_object = super_object
		self.contents = contents
	
	def _allows_extra_data_(self) -> bool:
		return True
	
	def _add_extra_field_(self, field: TypedGroup) -> None:
		self.contents.append(field)
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(clazz={self.clazz!r}, super_object={self.super_object!r}, contents={self.contents!r})"
	
	def _as_multiline_string_header_(self) -> str:
		header = f"object of class {self.clazz}"
		if self.super_object is None and not self.contents:
			header += ", no contents"
		return header
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		if self.super_object is not None:
			yield from advanced_repr.as_multiline_string(self.super_object, prefix="super object: ")
		for value in self.contents:
			yield from advanced_repr.as_multiline_string(value)


# False positive from flake8-bugbear, see:
# https://github.com/PyCQA/flake8-bugbear/issues/280
class _KnownArchivedClass(abc.ABCMeta): # noqa: B024
	"""Metaclass for :class:`KnownArchivedObject`."""
	
	def __instancecheck__(self, instance: typing.Any) -> bool:
		"""Adds a special case for :class:`GenericArchivedObject`:
		if its :attr:`~GenericArchivedObject.super_object` is an instance of this class,
		then the entire :class:`GenericArchivedObject` is also considered an instance of this class.
		
		This simplifies isinstance checks in unarchiving methods
		where objects might have an unknown concrete class with a known superclass.
		"""
		
		return super().__instancecheck__(instance) or (isinstance(instance, GenericArchivedObject) and isinstance(instance.super_object, self))


class KnownArchivedObject(metaclass=_KnownArchivedClass):
	# archived_name is set by __init_subclass__ on each subclass.
	archived_name: typing.ClassVar[bytes]
	
	@classmethod
	def __init_subclass__(cls) -> None:
		super().__init_subclass__()
		
		# Set archived_name only if it hasn't already been set manually.
		# Have to check directly in __dict__ instead of with try/except AttributeError or hasattr,
		# because otherwise the archived_name from superclasses would be detected
		# even archived_name on the class itself hasn't been set manually.
		if "archived_name" not in cls.__dict__:
			cls.archived_name = cls.__name__.encode("ascii")
		
		# Ditto for init_from_unarchiver.
		if "init_from_unarchiver" not in cls.__dict__:
			base_cls_unchecked = cls.__bases__[0]
			if not issubclass(base_cls_unchecked, KnownArchivedObject):
				raise TypeError(f"The first base class of an archived class must be KnownArchivedObject or a subclass of it (found {base_cls_unchecked})")
			
			# Workaround for https://github.com/python/mypy/issues/2608 -
			# the check above narrows the type of base_cls_unchecked,
			# but mypy doesn't pass the narrowed type into closures.
			# So as a workaround assign the type-narrowed value to a new variable,
			# which always has the specific type and isn't narrowed using a check,
			# so mypy recognizes its type inside the closure as well.
			base_cls = base_cls_unchecked
			
			# Provide a default init_from_unarchiver implementation
			# that checks that the superclass in the archived class information matches the one in Python,
			# calls init_from_unarchiver in the superclass (if there is one),
			# and finally calls the class's own _init_from_unarchiver_ implementation.
			def init_from_unarchiver(self: KnownArchivedObject, unarchiver: Unarchiver, archived_class: Class) -> None:
				if base_cls == KnownArchivedObject:
					# This is the root class (for archiving purposes) in the Python hierarchy.
					# Ensure that the same is true for the archived class.
					if archived_class.superclass is not None:
						raise ValueError(f"Class {archived_class.name!r} should have no superclass, but unexpectedly has one in the typedstream: {archived_class}")
				else:
					# This class has a superclass (for archiving purposes) in the Python hierarchy.
					# Ensure that the archived class also has one and that the names match.
					if archived_class.superclass is None:
						raise ValueError(f"Class {archived_class.name!r} should have superclass {base_cls.archived_name!r}, but has no superclass in the typedstream")
					elif archived_class.superclass.name != base_cls.archived_name:
						raise ValueError(f"Class {archived_class.name!r} should have superclass {base_cls.archived_name!r}, but has a different superclass in the typedstream: {archived_class}")
					
					base_cls.init_from_unarchiver(self, unarchiver, archived_class.superclass)
				
				# Ensure that the class defines its own _init_from_unarchiver_
				# and doesn't just inherit the superclass's implementation,
				# because that would result in the superclass's implementation being called more than once.
				# It also enforces that every class checks its own version number,
				# even if it doesn't have any data other than that belonging to the superclass
				# (because in another version it might have data of its own).
				if "_init_from_unarchiver_" not in cls.__dict__:
					raise ValueError("Every KnownArchivedObject must define its own _init_from_unarchiver_ implementation - inheriting it from the superclass is not allowed")
				
				cls._init_from_unarchiver_(self, unarchiver, archived_class.version)
			
			cls.init_from_unarchiver = init_from_unarchiver # type: ignore # mypy doesn't want you to assign to methods (it's fine here, our replacement has an identical signature)
	
	@abc.abstractmethod
	def _init_from_unarchiver_(self, unarchiver: "Unarchiver", class_version: int) -> None:
		"""Initialize ``self`` by reading archived data from a typedstream.
		
		This method must be implemented in *every* class that inherits (directly or indirectly) from KnownArchivedObject.
		Inheriting the implementation of a superclass is not allowed.
		This is to ensure that every class checks its version number.
		
		Implementations of this method should only read data belonging to the class itself.
		They shouldn't read any data belonging to the class's superclasses (if any),
		and they shouldn't manually call the superclass's :func:`_init_from_unarchiver_` implementation.
		The internals of :class:`KnownArchivedObject`
		ensure that all classes in the superclass chain have their :func:`_init_from_unarchiver_` implementations called,
		with the appropriate arguments and in the correct order
		(superclasses before their subclasses).
		
		:param unarchiver: The unarchiver from which to read archived data.
		:param class_version: The version of the class that archived the data.
			A change in the class version number normally indicates that the data format has changed,
			so implementations should check that the version number has the expected value
			(or one of multiple expected values,
			if there are multiple known versions of the data format)
			and raise an exception otherwise.
		"""
		
		raise NotImplementedError()
	
	# An override of init_from_unarchiver is defined by __init_subclass__ on each subclass.
	# It can also be overridden manually in subclasses,
	# in case the default implementation isn't suitable,
	# for example if there is archived data belonging to the subclass before that belonging to the superclasses.
	# In that case the implementation needs to manually perform all checks that would be performed by the automatic implementation,
	# like checking the superclass name in the archived class information.
	def init_from_unarchiver(self, unarchiver: "Unarchiver", archived_class: Class) -> None:
		# Raise something other than NotImplementedError - this method normally doesn't need to be implemented manually by the user.
		# (PyCharm for example warns when a subclass doesn't override a method that raises NotImplementedError.)
		raise AssertionError("This implementation should never be called. It should have been overridden automatically by __init_subclass__.")
	
	def _allows_extra_data_(self) -> bool:
		return False
	
	def _add_extra_field_(self, field: TypedGroup) -> None:
		raise TypeError(f"{_object_class_name(self)} does not allow extra data at the end of the object")
	
	def __repr__(self) -> str:
		class_name = _object_class_name(self)
		if KnownArchivedObject in type(self).__bases__:
			# This is an instance of a root class (e. g. NSObject, Object),
			# which generally contains no interesting data of its own,
			# so omit the ellipsis here.
			return f"<{class_name}>"
		else:
			return f"<{class_name} ...>"


archived_classes_by_name: typing.Dict[bytes, typing.Type[KnownArchivedObject]] = {}


def register_archived_class(python_class: typing.Type[KnownArchivedObject]) -> None:
	archived_classes_by_name[python_class.archived_name] = python_class


_KAO = typing.TypeVar("_KAO", bound=KnownArchivedObject)


def archived_class(python_class: typing.Type[_KAO]) -> typing.Type[_KAO]:
	register_archived_class(python_class)
	return python_class


def lookup_archived_class(archived_class: Class) -> typing.Tuple[typing.Type[KnownArchivedObject], Class]:
	"""Try to find the Python class corresponding to the given archived class.
	
	If the class cannot be found,
	this function automatically tries to look up the superclass instead,
	continuing recursively until a known class is encountered.
	
	:param archived_class: The archived class to look up.
	:return: A tuple of the found Python class and its corresponding archived class.
		The latter may be different from the ``archived_class`` parameter
		if the exact class was not found,
		but one of its superclasses was.
	:raises LookupError: If no Python class could be found for any class in the superclass chain.
	"""
	
	found_superclass: typing.Optional[Class] = archived_class
	while found_superclass is not None:
		try:
			return archived_classes_by_name[found_superclass.name], found_superclass
		except KeyError:
			found_superclass = found_superclass.superclass
	
	raise LookupError(f"No Python class has been registered for any class in the superclass chain: {archived_class}")


def instantiate_archived_class(archived_class: Class) -> typing.Tuple[typing.Union[GenericArchivedObject, KnownArchivedObject], typing.Optional[Class]]:
	# Try to look up a known custom Python class for the archived class
	# (or alternatively one of its superclasses).
	python_class: typing.Optional[typing.Type[KnownArchivedObject]]
	superclass: typing.Optional[Class]
	try:
		python_class, superclass = lookup_archived_class(archived_class)
	except LookupError:
		python_class = None
		superclass = None
	
	if python_class is None:
		# No Python class was found for any part of the superclass chain -
		# create a generic object instead.
		return GenericArchivedObject(archived_class, None, []), superclass
	elif superclass != archived_class:
		# No Python class was found that matches the archived class exactly,
		# but one of its superclasses was found -
		# create an instance of that,
		# so that at least part of the object can be decoded properly.
		# The fields that are not part of any known class
		# are stored in a generic object.
		return GenericArchivedObject(archived_class, python_class(), []), superclass
	else:
		# A Python class was found that corresponds exactly to the archived class,
		# so create an instance of it.
		return python_class(), superclass


class GenericStruct(advanced_repr.AsMultilineStringBase):
	"""Representation of a generic C struct value as it is stored in a typedstream.
	
	This class is only used for struct values whose struct type is not known.
	Structs of known types are represented as instances of custom Python classes instead.
	"""
	
	name: typing.Optional[bytes]
	fields: typing.List[typing.Any]
	
	def __init__(self, name: typing.Optional[bytes], fields: typing.List[typing.Any]) -> None:
		super().__init__()
		
		self.name = name
		self.fields = fields
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, fields={self.fields!r})"
	
	def _as_multiline_string_header_(self) -> str:
		if self.name is None:
			decoded_name = "(no name)"
		else:
			decoded_name = self.name.decode("ascii", errors="backslashreplace")
		return f"struct {decoded_name}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for field_value in self.fields:
			yield from advanced_repr.as_multiline_string(field_value)


_KS = typing.TypeVar("_KS", bound="KnownStruct")


class KnownStruct(object):
	struct_name: typing.ClassVar[bytes]
	field_encodings: typing.ClassVar[typing.Sequence[bytes]]
	encoding: typing.ClassVar[bytes]
	
	def __init_subclass__(cls) -> None:
		super().__init_subclass__()
		
		cls.encoding = encodings.build_struct_encoding(cls.struct_name, cls.field_encodings)


struct_classes_by_encoding: typing.Dict[bytes, typing.Type[KnownStruct]] = {}


def register_struct_class(python_class: typing.Type[KnownStruct]) -> None:
	struct_classes_by_encoding[python_class.encoding] = python_class


def struct_class(python_class: typing.Type[_KS]) -> typing.Type[_KS]:
	register_struct_class(python_class)
	return python_class


def _class_name(cls: typing.Type[typing.Any]) -> str:
	if issubclass(cls, KnownArchivedObject):
		return cls.archived_name.decode("ascii", errors="backslashreplace")
	elif issubclass(cls, KnownStruct) and cls.struct_name != b"?":
		return cls.struct_name.decode("ascii", errors="backslashreplace")
	else:
		return cls.__name__


def _object_class_name(obj: typing.Any) -> str:
	if isinstance(obj, GenericArchivedObject):
		return obj.clazz.name.decode("ascii", errors="backslashreplace")
	elif isinstance(obj, GenericStruct) and obj.name is not None and obj.name != b"?":
		return obj.name.decode("ascii", errors="backslashreplace")
	else:
		return _class_name(type(obj))


# Placeholder for unset lookahead parameters.
# Cannot use None for this,
# because None is a valid event.
_NO_LOOKAHEAD = object()


class Unarchiver(typing.ContextManager["Unarchiver"]):
	reader: stream.TypedStreamReader
	_close_reader: bool
	_lookahead: typing.Any
	shared_object_table: typing.List[typing.Tuple[stream.ObjectReference.Type, typing.Any]]
	
	@classmethod
	def from_data(cls, data: bytes) -> "Unarchiver":
		"""Create an unarchiver for the given typedstream data."""
		
		return cls(stream.TypedStreamReader.from_data(data), close=True)
	
	@classmethod
	def from_stream(cls, f: typing.BinaryIO, *, close: bool = False) -> "Unarchiver":
		"""Create an unarchiver for the typedstream data in the given byte stream.
		
		:param f: The byte stream from which to decode data.
		:param close: Controls whether the raw stream should also be closed when :meth:`close` is called.
			By default this is ``False`` and callers are expected to close the raw stream themselves after closing the :class:`Unarchiver`.
		"""
		
		return cls(stream.TypedStreamReader(f, close=close), close=True)
	
	@classmethod
	def open(cls, filename: typing.Union[str, bytes, os.PathLike]) -> "Unarchiver":
		"""Create an unarchiver for the typedstream file at the given path."""
		
		return cls(stream.TypedStreamReader.open(filename), close=True)
	
	def __init__(self, reader: stream.TypedStreamReader, *, close: bool = False) -> None:
		"""Create an :class:`Unarchiver` that decodes data based on events from the given low-level :class:`~typedstream.archiving.TypedStreamReader`.
		
		:param reader: The low-level reader from which to read the typedstream events.
		:param close: Controls whether the low-level reader should also be closed when :meth:`close` is called.
			By default this is ``False`` and callers are expected to close the reader themselves after closing the :class:`Unarchiver`.
		"""
		
		super().__init__()
		
		self.reader = reader
		self._close_reader = close
		self.shared_object_table = []
	
	def __enter__(self) -> "Unarchiver":
		return self
	
	def __exit__(
		self,
		exc_type: typing.Optional[typing.Type[BaseException]],
		exc_val: typing.Optional[BaseException],
		exc_tb: typing.Optional[types.TracebackType],
	) -> typing.Optional[bool]:
		self.close()
		return None
	
	def close(self) -> None:
		"""Close this :class:`Unarchiver`.
		
		If ``close=True`` was passed when this :class:`Unarchiver` was created,
		the underlying :class:`~typedstream.archiving.TypedStreamReader`'s ``close`` method is called as well.
		"""
		
		if self._close_reader:
			self.reader.close()
	
	def _lookup_reference(self, ref: stream.ObjectReference) -> typing.Any:
		ref_type, obj = self.shared_object_table[ref.number]
		if ref.referenced_type != ref_type:
			raise ValueError(f"Object reference type mismatch: reference should point to an object of type {ref.referenced_type.value}, but the referenced object number {ref.number} has type {ref_type.value}")
		return obj
	
	def decode_any_untyped_value(self, expected_encoding: bytes) -> typing.Any:
		first = next(self.reader)
		
		if first is None or isinstance(first, (int, float, bytes)):
			return first
		elif isinstance(first, stream.ObjectReference):
			return self._lookup_reference(first)
		elif isinstance(first, stream.CString):
			self.shared_object_table.append((stream.ObjectReference.Type.C_STRING, first.contents))
			return first.contents
		elif isinstance(first, stream.Atom):
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
			
			archived_class = self.decode_any_untyped_value(b"#")
			if not isinstance(archived_class, Class):
				raise ValueError(f"Object class must be a Class, not {type(archived_class)}")
			
			# Create the object.
			obj, superclass = instantiate_archived_class(archived_class)
			known_obj: typing.Optional[KnownArchivedObject]
			if isinstance(obj, GenericArchivedObject):
				known_obj = obj.super_object
			else:
				known_obj = obj
			
			# Now that the object is created,
			# replace the placeholder in the shared object table with the real object.
			self.shared_object_table[placeholder_index] = (stream.ObjectReference.Type.OBJECT, obj)
			
			if known_obj is not None:
				assert superclass is not None
				known_obj.init_from_unarchiver(self, superclass)
			
			next_event = next(self.reader)
			if obj._allows_extra_data_():
				# At least part of the object is not known,
				# so there may be extra trailing data
				# that should be stored in the generic part of the object.
				while not isinstance(next_event, stream.EndObject):
					obj._add_extra_field_(self.decode_typed_values(_lookahead=next_event))
					next_event = next(self.reader)
			else:
				# The object's exact class is fully known,
				# so there shouldn't be any extra data at the end of the object.
				if not isinstance(next_event, stream.EndObject):
					raise ValueError(f"Expected EndObject after fully known archived object, not {type(next_event)}")
			
			return obj
		elif isinstance(first, stream.ByteArray):
			return Array(first.data)
		elif isinstance(first, stream.BeginArray):
			_, expected_element_encoding = encodings.parse_array_encoding(expected_encoding)
			array = Array([self.decode_any_untyped_value(expected_element_encoding) for _ in range(first.length)])
			
			end = next(self.reader)
			if not isinstance(end, stream.EndArray):
				raise ValueError(f"Expected EndArray, not {type(end)}")
			
			return array
		elif isinstance(first, stream.BeginStruct):
			python_struct_class: typing.Optional[typing.Type[KnownStruct]]
			try:
				python_struct_class = struct_classes_by_encoding[expected_encoding]
			except KeyError:
				python_struct_class = None
				_, expected_field_encodings = encodings.parse_struct_encoding(expected_encoding)
			else:
				expected_field_encodings = python_struct_class.field_encodings
			
			fields = [self.decode_any_untyped_value(expected) for expected in expected_field_encodings]
			
			end = next(self.reader)
			if not isinstance(end, stream.EndStruct):
				raise ValueError(f"Expected EndStruct, not {type(end)}")
			
			if python_struct_class is None:
				return GenericStruct(first.name, fields)
			else:
				return python_struct_class(*fields)
		else:
			raise ValueError(f"Unexpected event at beginning of untyped value: {type(first)}")
	
	def decode_typed_values(self, _lookahead: typing.Any = _NO_LOOKAHEAD) -> TypedGroup:
		"""Decode a group of typed values from the typedstream.
		
		The number of values in the group and their types are read dynamically from the type information in the typedstream.
		
		There's no Objective-C equivalent for this method -
		``NSUnarchiver`` only supports decoding values whose types are known beforehand.
		"""
		
		if _lookahead is _NO_LOOKAHEAD:
			begin = next(self.reader)
		else:
			begin = _lookahead
		
		if not isinstance(begin, stream.BeginTypedValues):
			raise ValueError(f"Expected BeginTypedValues, not {type(begin)}")
		
		ret: TypedGroup
		if len(begin.encodings) == 1:
			# Single typed values are quite common,
			# so use a special subclass that's more convenient to use.
			ret = TypedValue(begin.encodings[0], self.decode_any_untyped_value(begin.encodings[0]))
		else:
			ret = TypedGroup(
				begin.encodings,
				[self.decode_any_untyped_value(encoding) for encoding in begin.encodings],
			)
		
		end = next(self.reader)
		if not isinstance(end, stream.EndTypedValues):
			raise ValueError(f"Expected EndTypedValues, not {type(end)}")
		
		return ret
	
	def decode_values_of_types(self, *type_encodings: typing.Union[bytes, typing.Type[KnownArchivedObject]]) -> typing.Sequence[typing.Any]:
		"""Decode a group of typed values from the typedstream,
		which must have the given type encodings.
		
		This method is roughly equivalent to the Objective-C method ``-[NSUnarchiver decodeValuesOfObjCTypes:]``.
		
		This method only supports decoding groups with known type encodings.
		To decode values of unknown type or a group containing an unknown number of values,
		use :func:`decode_typed_values`.
		"""
		
		if not type_encodings:
			raise TypeError("Expected at least one type encoding")
		
		expected_type_encodings = []
		for enc in type_encodings:
			if isinstance(enc, type):
				expected_type_encodings.append(b"@")
			else:
				expected_type_encodings.append(enc)
		
		group = self.decode_typed_values()
		
		if not encodings.all_encodings_match_expected(group.encodings, expected_type_encodings):
			raise ValueError(f"Expected type encodings {expected_type_encodings}, but got type encodings {group.encodings} in stream")
		
		for enc, obj in zip(type_encodings, group.values):
			if obj is not None and isinstance(enc, type) and not isinstance(obj, enc):
				raise TypeError(f"Expected object of class {_class_name(enc)}, but got class {_object_class_name(obj)} in stream")
		
		return group.values
	
	def decode_value_of_type(self, type_encoding: typing.Union[bytes, typing.Type[KnownArchivedObject]]) -> typing.Any:
		"""Decode a single typed value from the typedstream,
		which must have the given type encoding.
		
		This method is roughly equivalent to the Objective-C method ``-[NSUnarchiver decodeValueOfObjCType:at:]``.
		
		This method only supports decoding single values with a known type encoding.
		To decode groups of more than one value,
		use :func:`decode_values_of_types`.
		To decode values of unknown type or a group containing an unknown number of values,
		use :func:`decode_typed_values`.
		"""
		
		(value,) = self.decode_values_of_types(type_encoding)
		return value
	
	def decode_array(self, element_type_encoding: bytes, length: int) -> Array:
		return self.decode_value_of_type(encodings.build_array_encoding(length, element_type_encoding))
	
	def decode_data_object(self) -> bytes:
		"""Decode a data object from the typedstream.
		
		This method is equivalent to the Objective-C method ``-[NSUnarchiver decodeDataObject]``.
		"""
		
		length = self.decode_value_of_type(b"i")
		if length < 0:
			raise ValueError(f"Data object length cannot be negative: {length}")
		data_array = self.decode_array(b"c", length)
		assert isinstance(data_array.elements, bytes)
		return data_array.elements
	
	def decode_property_list(self) -> typing.Any:
		"""Decode a property list (in old binary plist format) from the typedstream.
		
		This method is equivalent to the Objective-C method ``-[NSUnarchiver decodePropertyList]``.
		"""
		
		return old_binary_plist.deserialize(self.decode_data_object())
	
	def decode_all(self) -> typing.Sequence[TypedGroup]:
		"""Decode the entire contents of the typedstream."""
		
		contents = []
		
		while True:
			try:
				lookahead = next(self.reader)
			except StopIteration:
				break
			
			contents.append(self.decode_typed_values(_lookahead=lookahead))
		
		return contents
	
	def decode_single_root(self) -> typing.Any:
		"""Decode the single root value in this unarchiver's typedstream.
		
		:raise ValueError: If the stream doesn't contain exactly one root value.
		"""
		
		values = self.decode_all()
		
		if not values:
			raise ValueError("Archive contains no values")
		elif len(values) > 1:
			raise ValueError(f"Archive contains {len(values)} root values (expected exactly one root value)")
		else:
			(root_group,) = values
			if not isinstance(root_group, TypedValue):
				raise ValueError(f"Archive's root value is a group of {len(root_group.values)} values (expected exactly one root value)")
			return root_group.value


def unarchive_from_stream(f: typing.BinaryIO) -> typing.Any:
	"""Unarchive the given binary data stream containing a single archived root value.
	
	:raise ValueError: If the stream doesn't contain exactly one root value.
	"""
	
	with Unarchiver.from_stream(f) as unarchiver:
		return unarchiver.decode_single_root()


def unarchive_from_data(data: bytes) -> typing.Any:
	"""Unarchive the given data containing a single archived root value.
	
	:raise ValueError: If the data doesn't contain exactly one root value.
	"""
	
	with Unarchiver.from_data(data) as unarchiver:
		return unarchiver.decode_single_root()


def unarchive_from_file(path: typing.Union[str, bytes, os.PathLike]) -> typing.Any:
	"""Unarchive the given file containing a single archived root value.
	
	:raise ValueError: If the file doesn't contain exactly one root value.
	"""
	
	with Unarchiver.open(path) as unarchiver:
		return unarchiver.decode_single_root()

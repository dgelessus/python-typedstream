import abc
import os
import types
import typing

from . import advanced_repr
from . import encodings
from . import old_binary_plist
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


class GenericArchivedObject(advanced_repr.AsMultilineStringBase):
	"""Representation of a generic object as it is stored in a typedstream.
	
	This class is only used for archived objects whose class is not known.
	Objects of known classes are represented as instances of custom Python classes instead.
	"""
	
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


class KnownArchivedObject(metaclass=abc.ABCMeta):
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
			
			# PyCharm doesn't understand that type: ignore comments can go anywhere,
			# unlike normal type declaration comments.
			# noinspection PyTypeHints
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


archived_classes_by_name: typing.Dict[bytes, typing.Type[KnownArchivedObject]] = {}


def register_archived_class(python_class: typing.Type[KnownArchivedObject]) -> None:
	archived_classes_by_name[python_class.archived_name] = python_class


_KAO = typing.TypeVar("_KAO", bound=KnownArchivedObject)


def archived_class(python_class: typing.Type[_KAO]) -> typing.Type[_KAO]:
	register_archived_class(python_class)
	return python_class


class GenericStruct(advanced_repr.AsMultilineStringBase):
	"""Representation of a generic C struct value as it is stored in a typedstream.
	
	This class is only used for struct values whose struct type is not known.
	Structs of known types are represented as instances of custom Python classes instead.
	"""
	
	name: bytes
	fields: typing.List[typing.Any]
	
	def __init__(self, name: bytes, fields: typing.List[typing.Any]) -> None:
		super().__init__()
		
		self.name = name
		self.fields = fields
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, fields={self.fields!r})"
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		yield f"struct {self.name.decode('ascii', errors='backslashreplace')}:"
		for field_value in self.fields:
			for line in advanced_repr.as_multiline_string(field_value, calling_self=self, state=state):
				yield "\t" + line


_KS = typing.TypeVar("_KS", bound="KnownStruct")


class KnownStruct(metaclass=abc.ABCMeta):
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
		"""Create an :class:`Unarchiver` that decodes data based on events from the given low-level :class:`~typedstream.archiver.TypedStreamReader`.
		
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
		the underlying :class:`~typedstream.archiver.TypedStreamReader`'s ``close`` method is called as well.
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
			# Try to look up a known custom Python class for the archived class and create an instance of it.
			# If no custom class is known for the archived class,
			# create a generic object instead.
			obj: typing.Union[GenericArchivedObject, KnownArchivedObject]
			try:
				python_class = archived_classes_by_name[archived_class.name]
			except KeyError:
				obj = GenericArchivedObject(archived_class, [])
			else:
				obj = python_class()
			
			# Now that the object is created,
			# replace the placeholder in the shared object table with the real object.
			self.shared_object_table[placeholder_index] = (stream.ObjectReference.Type.OBJECT, obj)
			
			if isinstance(obj, GenericArchivedObject):
				next_event = next(self.reader)
				while not isinstance(next_event, stream.EndObject):
					obj.contents.append(self.decode_typed_values(_lookahead=next_event))
					next_event = next(self.reader)
			else:
				obj.init_from_unarchiver(self, archived_class)
				end = next(self.reader)
				if not isinstance(end, stream.EndObject):
					raise ValueError(f"Expected EndObject, not {type(end)}")
			
			return obj
		elif isinstance(first, stream.ByteArray):
			return first.data
		elif isinstance(first, stream.BeginArray):
			_, expected_element_encoding = encodings.parse_array_encoding(expected_encoding)
			array = [self.decode_any_untyped_value(expected_element_encoding) for _ in range(first.length)]
			
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
	
	def decode_typed_values(self, *expected_encodings: bytes, _lookahead: typing.Any = _NO_LOOKAHEAD) -> typing.Any:
		if _lookahead is _NO_LOOKAHEAD:
			begin = next(self.reader)
		else:
			begin = _lookahead
		
		if not isinstance(begin, stream.BeginTypedValues):
			raise ValueError(f"Expected BeginTypedValues, not {type(begin)}")
		
		if expected_encodings:
			if not encodings.all_encodings_match_expected(begin.encodings, expected_encodings):
				raise ValueError(f"Expected type encodings {expected_encodings}, but got type encodings {begin.encodings} in stream")
		else:
			# Needs to be converted to a tuple to make mypy happy
			# (*args are implicitly typed as tuples).
			expected_encodings = tuple(begin.encodings)
		
		if len(begin.encodings) == 1:
			# Single typed values are quite common,
			# so for convenience don't wrap them in a 1-element tuple.
			ret = self.decode_any_untyped_value(expected_encodings[0])
		else:
			ret = Group(self.decode_any_untyped_value(expected) for expected in expected_encodings)
		
		end = next(self.reader)
		if not isinstance(end, stream.EndTypedValues):
			raise ValueError(f"Expected EndTypedValues, not {type(end)}")
		
		return ret
	
	def decode_array(self, element_type_encoding: bytes, length: int) -> typing.Any:
		# Actually always returns a sequence,
		# but a more specific return type than Any makes this method annoying to use.
		return self.decode_typed_values(encodings.build_array_encoding(length, element_type_encoding))
	
	def decode_property_list(self) -> typing.Any:
		length = self.decode_typed_values(b"i")
		if length < 0:
			raise ValueError(f"Property list data length cannot be negative: {length}")
		data = self.decode_array(b"c", length)
		return old_binary_plist.deserialize(data)
	
	def decode_all(self) -> typing.Sequence[typing.Any]:
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
			return values[0]


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

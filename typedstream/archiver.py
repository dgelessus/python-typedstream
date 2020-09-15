import abc
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
	# archived_name is set by register_archived_class on each registered subclass.
	archived_name: typing.ClassVar[bytes]
	
	def _init_from_unarchiver_(self, unarchiver: "Unarchiver", archived_class: Class) -> None:
		"""Initialize ``self`` by reading archived data from a typedstream.
		
		This method must be implemented in *every* class that inherits (directly or indirectly) from KnownArchivedObject.
		Inheriting the implementation of a superclass is not allowed.
		This is to ensure that every class checks its version number.
		
		Implementations of this method should only read data belonging to the class itself.
		They shouldn't read any data belonging to the class's superclasses (if any),
		and they shouldn't manually call the superclass's :func:`_init_from_unarchiver_` implementation.
		The internals of :class:`Unarchiver` (or :func:`register_archived_class` to be exact)
		ensure that all classes in the superclass chain have their :func:`_init_from_unarchiver_` implementations called,
		with the appropriate arguments and in the correct order
		(superclasses before their subclasses).
		
		:param unarchiver: The unarchiver from which to read archived data.
		:param archived_class: Information about the current class,
			as stored in the typedstream.
			Implementations of this method should check the :attr:`~Class.version` attribute in particular,
			to determine what structure the object data will have,
			and should raise an exception if the version number is not supported.
			The rest of the class information (name and superclass)
			has already been checked automatically by the time that this method is called,
			so this information doesn't need to be checked manually by implementations.
		"""
		
		raise NotImplementedError()
	
	# An override of init_from_unarchiver is defined by register_archived_class on each registered subclass.
	# It can also be overridden manually in subclasses,
	# in case the default implementation isn't suitable,
	# for example if there is archived data belonging to the subclass before that belonging to the superclasses.
	# In that case the implementation needs to manually perform all checks that would be performed by the automatic implementation,
	# like checking the superclass name in the archived class information.
	def init_from_unarchiver(self, unarchiver: "Unarchiver", archived_class: Class) -> None:
		# Raise something other than NotImplementedError - this method normally doesn't need to be implemented manually by the user.
		# (PyCharm for example warns when a subclass doesn't override a method that raises NotImplementedError.)
		raise AssertionError("This implementation should never be called. It should have been overridden automatically by register_archived_class.")


archived_classes_by_name: typing.Dict[bytes, typing.Type[KnownArchivedObject]] = {}


def register_archived_class(python_class: typing.Type[KnownArchivedObject]) -> None:
	# Set archived_name only if it hasn't already been set manually.
	# Have to check directly in __dict__ instead of with try/except AttributeError or hasattr,
	# because otherwise the archived_name from superclasses would be detected
	# even archived_name on the class itself hasn't been set manually.
	if "archived_name" not in python_class.__dict__:
		python_class.archived_name = python_class.__name__.encode("ascii")
	
	# Ditto for init_from_unarchiver.
	if "init_from_unarchiver" not in python_class.__dict__:
		python_base_class_unchecked = python_class.__bases__[0]
		if not issubclass(python_base_class_unchecked, KnownArchivedObject):
			raise TypeError(f"The first base class of an archived class must be KnownArchivedObject or a subclass of it (found {python_base_class_unchecked})")
		
		# Workaround for https://github.com/python/mypy/issues/2608 -
		# the check above narrows the type of python_base_class_unchecked,
		# but mypy doesn't pass the narrowed type into closures.
		# So as a workaround assign the type-narrowed value to a new variable,
		# which always has the specific type and isn't narrowed using a check,
		# so mypy recognizes its type inside the closure as well.
		python_base_class = python_base_class_unchecked
		
		# Provide a default init_from_unarchiver implementation
		# that checks that the superclass in the archived class information matches the one in Python,
		# calls init_from_unarchiver in the superclass (if there is one),
		# and finally calls the class's own _init_from_unarchiver_ implementation.
		def init_from_unarchiver(self: KnownArchivedObject, unarchiver: Unarchiver, archived_class: Class) -> None:
			if python_base_class == KnownArchivedObject:
				# This is the root class (for archiving purposes) in the Python hierarchy.
				# Ensure that the same is true for the archived class.
				if archived_class.superclass is not None:
					raise ValueError(f"Class {archived_class.name!r} should have no superclass, but unexpectedly has one in the typedstream: {archived_class}")
			else:
				# This class has a superclass (for archiving purposes) in the Python hierarchy.
				# Ensure that the archived class also has one and that the names match.
				if archived_class.superclass is None:
					raise ValueError(f"Class {archived_class.name!r} should have superclass {python_base_class.archived_name!r}, but has no superclass in the typedstream")
				elif archived_class.superclass.name != python_base_class.archived_name:
					raise ValueError(f"Class {archived_class.name!r} should have superclass {python_base_class.archived_name!r}, but has a different superclass in the typedstream: {archived_class}")
				
				python_base_class.init_from_unarchiver(self, unarchiver, archived_class.superclass)
			
			# Ensure that the class defines its own _init_from_unarchiver_
			# and doesn't just inherit the superclass's implementation,
			# because that would result in the superclass's implementation being called more than once.
			# It also enforces that every class checks its own version number,
			# even if it doesn't have any data other than that belonging to the superclass
			# (because in another version it might have data of its own).
			if "_init_from_unarchiver_" not in python_class.__dict__:
				raise ValueError("Every KnownArchivedObject must define its own _init_from_unarchiver_ implementation - inheriting it from the superclass is not allowed")
			
			python_class._init_from_unarchiver_(self, unarchiver, archived_class)
		
		# PyCharm doesn't understand that type: ignore comments can go anywhere,
		# unlike normal type declaration comments.
		# noinspection PyTypeHints
		python_class.init_from_unarchiver = init_from_unarchiver # type: ignore # mypy doesn't want you to assign to methods (it's fine here, our replacement has an identical signature)
	
	archived_classes_by_name[python_class.archived_name] = python_class


_KAO = typing.TypeVar("_KAO", bound=KnownArchivedObject)


def archived_class(python_class: typing.Type[_KAO]) -> typing.Type[_KAO]:
	register_archived_class(python_class)
	return python_class


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
			
			archived_class = self.decode_any_untyped_value()
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
	
	def decode_typed_values(self, *expected_encodings: bytes, _lookahead: typing.Any = _NO_LOOKAHEAD) -> typing.Any:
		if _lookahead is _NO_LOOKAHEAD:
			begin = next(self.reader)
		else:
			begin = _lookahead
		
		if not isinstance(begin, stream.BeginTypedValues):
			raise ValueError(f"Expected BeginTypedValues, not {type(begin)}")
		elif expected_encodings and tuple(begin.encodings) != tuple(expected_encodings):
			raise ValueError(f"Expected type encodings {expected_encodings}, but got type encodings {begin.encodings} in stream")
		
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

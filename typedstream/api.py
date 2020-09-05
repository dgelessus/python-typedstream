import abc
import enum
import os
import struct
import types
import typing


_FLOAT_STRUCTS_BY_BYTE_ORDER = {
	"big": struct.Struct(">f"),
	"little": struct.Struct("<f"),
}

_DOUBLE_STRUCTS_BY_BYTE_ORDER = {
	"big": struct.Struct(">d"),
	"little": struct.Struct("<d"),
}

# This is the earliest streamer version still supported by Mac OS X.
# It is only produced by earlier versions of NeXTSTEP (unclear which).
STREAMER_VERSION_OLD_NEXTSTEP = 3
# This is the streamer version used by all versions of Mac OS X and later versions of NeXTSTEP.
# It is probably the last version to ever exist,
# as the typedstream format is effectively obsolete.
STREAMER_VERSION_CURRENT = 4

# Signature string for big-endian typedstreams.
SIGNATURE_BIG_ENDIAN = b"typedstream"
# Signature string for little-endian typedstreams.
SIGNATURE_LITTLE_ENDIAN = b"streamtyped"
# Both signature strings have the same length.
assert len(SIGNATURE_BIG_ENDIAN) == len(SIGNATURE_LITTLE_ENDIAN)
SIGNATURE_LENGTH = len(SIGNATURE_BIG_ENDIAN)

_SIGNATURE_TO_ENDIANNESS_MAP = {
	SIGNATURE_BIG_ENDIAN: "big",
	SIGNATURE_LITTLE_ENDIAN: "little",
}

# These values are taken from the NXSYSTEMVERSION constants
# from typedstream.h from an early (Darwin 0.1) version of the Objective-C runtime:
# https://sourceforge.net/projects/aapl-darwin/files/Darwin-0.1/objc-1.tar.gz/download
# These appear to correspond to early NeXTSTEP version numbers (0.8.x, 0.9.x).
SYSTEM_VERSION_NEXTSTEP_082 = 82
SYSTEM_VERSION_NEXTSTEP_083 = 83
SYSTEM_VERSION_NEXTSTEP_090 = 90
SYSTEM_VERSION_NEXTSTEP_0900 = 900
SYSTEM_VERSION_NEXTSTEP_0901 = 901
SYSTEM_VERSION_NEXTSTEP_0905 = 905
SYSTEM_VERSION_NEXTSTEP_0930 = 930
# This is the system version used by all versions of Mac OS X since at least 10.4
# (and probably earlier - if the numbering scheme is to be trusted, probably since NeXTSTEP 1.0).
SYSTEM_VERSION_MAC_OS_X = 1000

# In the original Darwin code,
# the term "label" is used ambiguously -
# both for the static integer constants listed below,
# and the dynamically assigned object reference numbers.
# For clarity,
# we use the following terminology:
# * A "reference number" is an integer (single-byte or multi-byte) that stands for a string or object stored earlier in the file.
# * A "tag" is one of the constant TAG_* values listed below.
# * A "head" is a single-byte value that stores either a single-byte reference number or a tag (indicating a literal string/object or a multi-byte reference number).

# Indicates an integer value, stored in 2 bytes.
TAG_INTEGER_2 = -127
# Indicates an integer value, stored in 4 bytes.
TAG_INTEGER_4 = -126
# Indicates a floating-point value, stored in 4 or 8 bytes (depending on whether it is a float or a double).
TAG_FLOATING_POINT = -125
# Indicates the start of a string value or an object that is stored literally and not as a backreference.
TAG_NEW = -124
# Indicates a nil value. Used for strings (unshared and shared), classes, and objects.
TAG_NIL = -123
# Indicates the end of an object.
TAG_END_OF_OBJECT = -122

# The lowest and highest values reserved for use as tags.
# Values outside this range are used to literally encode single-byte integers.
# Integer values that fall into the tag range must be encoded in two separate bytes using TAG_INTEGER_2
# so that they do not conflict with the tags.
FIRST_TAG = -128
LAST_TAG = -111
TAG_RANGE = range(FIRST_TAG, LAST_TAG + 1)
# The first reference number to be used.
# This has been chosen to be exactly one higher than the highest tag,
# so that early reference numbers can be encoded directly in the head.
FIRST_REFERENCE_NUMBER = LAST_TAG + 1


def _decode_reference_number(encoded: int) -> int:
	"""Decode a reference number (as stored in a typedstream) to a regular zero-based index."""
	
	return encoded - FIRST_REFERENCE_NUMBER


class InvalidTypedStreamError(Exception):
	"""Raised by :class:`TypedStreamReader` if the typedstream data is invalid or doesn't match the expected structure."""


# Adapted from https://github.com/beeware/rubicon-objc/blob/v0.3.1/rubicon/objc/types.py#L127-L188
# The type encoding syntax used in typedstreams is very similar,
# but not identical,
# to the one used by the Objective-C runtime.
# Some features are not used/supported in typedstreams,
# such as qualifiers, arbitrary pointers, object pointer class names, block pointers, etc.
# Typedstreams also use some type encoding characters that are not used by the Objective-C runtime,
# such as "+" for raw bytes and "%" for "atoms" (deduplicated/uniqued/interned C strings).
def _end_of_encoding(encoding: bytes, start: int) -> int:
	"""Find the end index of the encoding starting at index start.
	
	The encoding is not validated very extensively.
	There are no guarantees what happens for invalid encodings;
	an error may be raised,
	or a bogus end index may be returned.
	Callers are expected to check that the returned end index actually results in a valid encoding.
	"""
	
	if start not in range(len(encoding)):
		raise ValueError(f"Start index {start} not in range({len(encoding)})")
	
	paren_depth = 0
	
	i = start
	while i < len(encoding):
		c = encoding[i:i+1]
		if c in b"([{":
			# Opening parenthesis of some type, wait for a corresponding closing paren.
			# This doesn't check that the parenthesis *types* match
			# (only the *number* of closing parens has to match).
			paren_depth += 1
			i += 1
		elif paren_depth > 0:
			if c in b")]}":
				# Closing parentheses of some type.
				paren_depth -= 1
			i += 1
			if paren_depth == 0:
				# Final closing parenthesis, end of this encoding.
				return i
		else:
			# All other encodings consist of exactly one character.
			return i + 1
	
	if paren_depth > 0:
		raise ValueError(f"Incomplete encoding, missing {paren_depth} closing parentheses: {encoding!r}")
	else:
		raise ValueError(f"Incomplete encoding, reached end of string too early: {encoding!r}")


# Adapted from https://github.com/beeware/rubicon-objc/blob/v0.3.1/rubicon/objc/types.py#L430-L450
def _split_encodings(encodings: bytes) -> typing.Iterable[bytes]:
	"""Split apart multiple type encodings contained in a single encoding string."""
	
	start = 0
	while start < len(encodings):
		end = _end_of_encoding(encodings, start)
		yield encodings[start:end]
		start = end


class RecursiveReprState(object):
	"""Holds state during recursive calls to :func:`repr`/``__repr__``-like functions,
	to track which objects have already been rendered before or are currently still being rendered.
	
	This state is used to avoid infinite recursion in case of circular references,
	and to avoid rendering large data structures more than once.
	"""
	
	class _Context(typing.ContextManager[None]):
		state: "RecursiveReprState"
		obj: object
		
		def __init__(self, state: "RecursiveReprState", obj: object) -> None:
			super().__init__()
			
			self.state = state
			self.obj = obj
		
		def __enter__(self) -> None:
			if self.obj is not None:
				self.state.already_rendered_ids.add(id(self.obj))
				self.state.currently_rendering_ids.append(id(self.obj))
		
		def __exit__(
			self,
			exc_type: typing.Optional[typing.Type[BaseException]],
			exc_val: typing.Optional[BaseException],
			exc_tb: typing.Optional[types.TracebackType],
		) -> typing.Optional[bool]:
			if self.obj is not None:
				popped = self.state.currently_rendering_ids.pop()
				assert popped == id(self.obj)
			return None
	
	already_rendered_ids: typing.Set[int]
	currently_rendering_ids: typing.List[int]
	
	def __init__(self, already_seen_ids: typing.Set[int], ids_stack: typing.List[int]) -> None:
		super().__init__()
		
		self.already_rendered_ids = already_seen_ids
		self.currently_rendering_ids = ids_stack
	
	def _representing(self, obj: object) -> typing.ContextManager[None]:
		"""Create a context manager to indicate when the given object is being processed.
		
		When the context manager is entered,
		``id(obj)`` is added to :attr:`already_rendered_ids` and :attr:`currently_rendering_ids`.
		When it is exited,
		``id(obj)`` is removed again from :attr:`currently_rendering_ids` (but not from :attr:`already_rendered_ids`).
		"""
		
		return RecursiveReprState._Context(self, obj)


class AsMultilineStringBase(abc.ABC):
	"""Base class for classes that want to implement a custom multiline string representation,
	for use by :func:`as_multiline_string`.
	
	This also provides an implementation of ``__str__`` based on :meth:`~AsMultilineStringBase._as_multiline_string_`.
	"""
	
	@abc.abstractmethod
	def _as_multiline_string_(self, *, state: RecursiveReprState) -> typing.Iterable[str]:
		"""Convert ``self`` to a multiline string representation.
		
		This method should not be called directly -
		use :func:`as_multiline_string` instead.
		
		:param state: A state object used to track repeated or recursive calls for the same object.
		:return: The string representation as an iterable of lines (line terminators not included).
		"""
		
		raise NotImplementedError()
	
	def __str__(self) -> str:
		return "\n".join(self._as_multiline_string_(state=RecursiveReprState(set(), [])))


def as_multiline_string(
	obj: object,
	*,
	calling_self: typing.Optional[object] = None,
	state: typing.Optional[RecursiveReprState] = None,
) -> typing.Iterable[str]:
	"""Convert an object to a multiline string representation.
	
	If the object has an :meth:`~AsMultilineStringBase._as_multiline_string_` method,
	it is used to create the multiline string representation.
	Otherwise,
	the object is converted to a string using default :class:`str` conversion,
	and then split into an iterable of lines.
	
	:param obj: The object to represent.
	:param calling_self: The object that is asking for the representation.
		This must be set when calling from an :meth:`~AsMultilineStringBase._as_multiline_string_` implementation,
		so that repeated and recursive calls are tracked properly.
	:param state: A state object from an outer :func:`as_multiline_string` call.
		This must be set when calling from an :meth:`~AsMultilineStringBase._as_multiline_string_` implementation,
		so that repeated and recursive calls are tracked properly.
	:return: The string representation as an iterable of lines (line terminators not included).
	"""
	
	if isinstance(obj, AsMultilineStringBase):
		if state is None:
			state = RecursiveReprState(set(), [])
		
		with state._representing(calling_self):
			yield from obj._as_multiline_string_(state=state)
	else:
		yield from str(obj).splitlines()


class BeginTypedValues(object):
	"""Marks the beginning of a group of values prefixed by a type encoding string."""
	
	encodings: typing.Sequence[bytes]
	
	def __init__(self, encodings: typing.Sequence[bytes]) -> None:
		super().__init__()
		
		self.encodings = encodings
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.encodings!r})"
	
	def __str__(self) -> str:
		return f"begin typed values (types {self.encodings!r})"


class EndTypedValues(object):
	"""Marks the end of a group of values prefixed by a type encoding string.
	
	This event is provided for convenience and doesn't correspond to any data in the typedstream.
	"""
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}()"
	
	def __str__(self) -> str:
		return "end typed values"


class ObjectReference(object):
	"""A reference to a previously read object."""
	
	class Type(enum.Enum):
		"""Describes what type of object a reference refers to."""
		
		C_STRING = "C string"
		CLASS = "class"
		OBJECT = "object"
	
	referenced_type: "ObjectReference.Type"
	number: int
	
	def __init__(self, referenced_type: "ObjectReference.Type", number: int) -> None:
		super().__init__()
		
		self.referenced_type = referenced_type
		self.number = number
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.referenced_type}, {self.number!r})"
	
	def __str__(self) -> str:
		return f"<reference to {self.referenced_type.value} #{self.number}>"


class Selector(object):
	"""An Objective-C selector.
	
	This is a thin wrapper around a plain :class:`bytes` object.
	The wrapper class is used to distinguish selector values from untyped bytes.
	"""
	
	name: typing.Optional[bytes]
	
	def __init__(self, name: typing.Optional[bytes]) -> None:
		super().__init__()
		
		self.name = name
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.name!r})"
	
	def __str__(self) -> str:
		return f"selector: {self.name!r}"


class CString(object):
	"""Information about a C string as it is stored in a typedstream.
	
	This is a thin wrapper around a plain :class:`bytes` object.
	The wrapper class is used to distinguish typed C string values from untyped bytes.
	"""
	
	contents: bytes
	
	def __init__(self, contents: bytes) -> None:
		super().__init__()
		
		self.contents = contents
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.contents!r})"
	
	def __str__(self) -> str:
		return f"C string: {self.contents!r}"


class SingleClass(object):
	"""Information about a class (name and version),
	stored literally in a chain of superclasses in a typedstream.
	
	A class in a typedstream can be stored literally, as a reference, or be ``Nil``.
	A literally stored class is always followed by information about its superclass.
	If the superclass information is also stored literally,
	it is again followed by information about its superclass.
	This chain continues until a class is reached that has been stored before
	(in which case it is stored as a reference)
	or a root class is reached
	(in which case the superclass is ``Nil``).
	
	The beginning and end of such a chain of superclasses are not marked explicitly in a typedstream,
	and no events are generated when a superclass chain begins or ends.
	A superclass chain begins implicitly when a literally stored class is encountered
	(if no chain is already in progress),
	and the chain ends after the first non-literal (i. e. reference or ``Nil``) class.
	"""
	
	name: bytes
	version: int
	
	def __init__(self, name: bytes, version: int) -> None:
		super().__init__()
		
		self.name = name
		self.version = version
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, version={self.version})"
	
	def __str__(self) -> str:
		return f"class {self.name.decode('ascii', errors='backslashreplace')} v{self.version}"


class BeginObject(object):
	"""Marks the beginning of a literally stored object.
	
	This event is followed by information about the object's class,
	stored as a chain of class information (see :class:`SingleClass`).
	This class chain is followed by an arbitrary number of type-prefixed value groups,
	which represent the object's contents.
	The object ends when an :class:`EndObject` is encountered where the next value group would start.
	"""
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}()"
	
	def __str__(self) -> str:
		return "begin literal object"


class EndObject(object):
	"""Marks the end of a literally stored object."""
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}()"
	
	def __str__(self) -> str:
		return "end literal object"


class ByteArray(object):
	"""Represents an array of bytes (signed or unsigned char).
	
	For performance and simplicity,
	such arrays are read all at once and represented as a single event,
	instead of generating one event per element as for other array element types.
	"""
	
	element_encoding: bytes
	data: bytes
	
	def __init__(self, element_encoding: bytes, data: bytes) -> None:
		super().__init__()
		
		self.element_encoding = element_encoding
		self.data = data
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(element_encoding={self.element_encoding!r}, data={self.data!r})"
	
	def __str__(self) -> str:
		return f"byte array (element type {self.element_encoding!r}): {self.data!r}"


class BeginArray(object):
	"""Marks the beginning of an array.
	
	This event is provided for convenience and doesn't directly correspond to data in the typedstream.
	The array length and element type information provided in this event actually comes from the arrays's type encoding.
	
	This event is followed by the element values,
	which are not explicitly type-prefixed,
	as they all have the type specified in the array type encoding.
	The end of the array is not marked in the typedstream data,
	as it can be determined based on the length and element type,
	but for convenience,
	an :class:`EndArray` element is generated after the last array element.
	
	This event is *not* generated for arrays of bytes (signed or unsigned char) -
	such arrays are represented as single :class:`ByteArray` events instead.
	"""
	
	element_encoding: bytes
	length: int
	
	def __init__(self, element_encoding: bytes, length: int) -> None:
		super().__init__()
		
		self.element_encoding = element_encoding
		self.length = length
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(element_encoding={self.element_encoding!r}, length={self.length!r})"
	
	def __str__(self) -> str:
		return f"begin array (element type {self.element_encoding!r}, length {self.length})"


class EndArray(object):
	"""Marks the end of an array.
	
	This event is provided for convenience and doesn't correspond to any data in the typedstream.
	"""
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}()"
	
	def __str__(self) -> str:
		return "end array"


class BeginStruct(object):
	"""Marks the beginning of a struct.
	
	This event is provided for convenience and doesn't directly correspond to data in the typedstream.
	The struct name and field type information provided in this event actually comes from the struct's type encoding.
	
	This event is followed by the field values,
	which are not explicitly type-prefixed (unlike in objects),
	as their types are specified in the struct type encoding.
	The end of the struct is not marked in the typedstream data,
	as it can be determined based on the type information,
	but for convenience,
	an :class:`EndStruct` element is generated after the last struct field.
	"""
	
	name: bytes
	field_encodings: typing.Sequence[bytes]
	
	def __init__(self, name: bytes, field_encodings: typing.Sequence[bytes]) -> None:
		super().__init__()
		
		self.name = name
		self.field_encodings = field_encodings
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, field_encodings={self.field_encodings!r})"
	
	def __str__(self) -> str:
		return f"begin struct {self.name.decode('ascii', errors='backslashreplace')} (field types {self.field_encodings!r})"


class EndStruct(object):
	"""Marks the end of a struct.
	
	This event is provided for convenience and doesn't correspond to any data in the typedstream.
	"""
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}()"
	
	def __str__(self) -> str:
		return "end struct"


ReadEvent = typing.Optional[typing.Union[BeginTypedValues, EndTypedValues, int, float, ObjectReference, CString, Selector, bytes, SingleClass, BeginObject, EndObject, ByteArray, BeginArray, EndArray, BeginStruct, EndStruct]]


class TypedStreamReader(typing.ContextManager["TypedStreamReader"], typing.Iterable[ReadEvent]):
	"""Reads typedstream data from a raw byte stream."""
	
	_EOF_MESSAGE: typing.ClassVar[str] = "End of typedstream reached"
	
	_is_debug_on: bool
	_close_stream: bool
	_stream: typing.BinaryIO
	
	shared_string_table: typing.List[bytes]
	
	streamer_version: int
	byte_order: str
	system_version: int
	
	_events_iterator: typing.Iterator[ReadEvent]
	
	@classmethod
	def open(cls, filename: typing.Union[str, bytes, os.PathLike], **kwargs: typing.Any) -> "TypedStreamReader":
		"""Open the typedstream file at the given path.
		
		This function accepts the same keyword arguments as the normal :class:`TypedStreamReader` constructor,
		except for ``close``.
		When using :func:`TypedStreamReader.open`,
		the underlying raw byte stream is created and managed automatically -
		callers only need to manage (i. e. close) the :class:`TypedStreamReader`.
		"""
		
		if "close" in kwargs:
			raise TypeError("ResourceFile.open does not support the 'close' keyword argument")
		
		return cls(open(filename, "rb"), close=True, **kwargs)
	
	def __init__(self, stream: typing.BinaryIO, *, close: bool = False, debug: bool = False) -> None:
		"""Create a :class:`TypedStreamReader` that reads data from the given raw byte stream.
		
		:param stream: The raw byte stream from which to read the typedstream data.
		:param close: Controls whether the raw stream should also be closed when :meth:`close` is called.
			By default this is ``False`` and callers are expected to close the raw stream themselves after closing the :class:`TypedStreamReader`.
		:param debug: If true, print lots of debugging status information while reading the stream.
		"""
		
		super().__init__()
		
		self._is_debug_on = debug
		self._close_stream = close
		self._stream = stream
		
		self.shared_string_table = []
		
		try:
			self._read_header()
			self._events_iterator = self._read_all_values()
		except BaseException:
			self.close()
			raise
	
	def close(self) -> None:
		"""Close this :class:`TypedStreamReader`.
		
		If ``close=True`` was passed when this :class:`TypedStreamReader` was created, the underlying raw stream's ``close`` method is called as well.
		"""
		
		if self._close_stream:
			self._stream.close()
	
	def __enter__(self) -> "TypedStreamReader":
		return self
	
	def __exit__(
		self,
		exc_type: typing.Optional[typing.Type[BaseException]],
		exc_val: typing.Optional[BaseException],
		exc_tb: typing.Optional[types.TracebackType],
	) -> typing.Optional[bool]:
		self.close()
		return None
	
	def __repr__(self) -> str:
		return f"<{type(self).__module__}.{type(self).__qualname__} at {id(self):#x}: streamer version {self.streamer_version}, byte order {self.byte_order}, system version {self.system_version}>"
	
	def __iter__(self) -> typing.Iterator[ReadEvent]:
		return self._events_iterator
	
	def _debug(self, message: str) -> None:
		"""If this reader has debugging enabled (i. e. ``debug=True`` was passed to the constructor),
		print out the given message.
		Otherwise do nothing.
		"""
		
		# TODO Replace this with a proper logging mechanism.
		if self._is_debug_on:
			print(message)
	
	def _read_exact(self, byte_count: int) -> bytes:
		"""Read byte_count bytes from the raw stream and raise an exception if too few bytes are read
		(i. e. if EOF was hit prematurely).
		"""
		
		data = self._stream.read(byte_count)
		if len(data) != byte_count:
			raise InvalidTypedStreamError(f"Attempted to read {byte_count} bytes of data, but only got {len(data)} bytes")
		return data
	
	def _read_head_byte(self, head: typing.Optional[int] = None) -> int:
		"""Read a head byte.
		
		:param head: If ``None``, the head byte is read normally from the stream.
			Otherwise, the passed-in head byte is returned and no read is performed.
			This parameter is provided to simplify a common pattern in this class's internal methods,
			where methods that need to read a head byte
			can alternatively accept an already read head byte as a parameter
			and skip the read operation.
			This mechanism is used to allow a limited form of lookahead for the head byte,
			which is needed to parse string and object references and to detect end-of-object markers.
		:return: The read or passed in head byte.
		"""
		
		if head is None:
			head = int.from_bytes(self._read_exact(1), self.byte_order, signed=True)
			self._debug(f"Head byte: {head} ({head & 0xff:#x})")
		return head
	
	def _read_integer(self, head: typing.Optional[int] = None, *, signed: bool) -> int:
		"""Read a low-level integer value.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:param signed: Whether to treat the integer as signed or unsigned.
		:return: The decoded integer value.
		"""
		
		self._debug("Standalone integer")
		head = self._read_head_byte(head)
		if head not in TAG_RANGE:
			if signed:
				v = head
			else:
				v = head & 0xff
			self._debug(f"\t... literal integer in head: {v}")
			return v
		elif head == TAG_INTEGER_2:
			v = int.from_bytes(self._read_exact(2), self.byte_order, signed=signed)
			self._debug(f"\t... literal integer in 2 bytes: {v} ({v:#x})")
			return v
		elif head == TAG_INTEGER_4:
			v = int.from_bytes(self._read_exact(4), self.byte_order, signed=signed)
			self._debug(f"\t... literal integer in 4 bytes: {v} ({v:#x})")
			return v
		else:
			raise InvalidTypedStreamError(f"Invalid head tag in this context: {head} ({head & 0xff:#x}")
	
	def _read_header(self) -> None:
		"""Read the typedstream file header (streamer version, signature/byte order indicator, system version).
		
		This is called only once,
		as part of :meth:`__init__`.
		"""
		
		(self.streamer_version, signature_length) = self._read_exact(2)
		self._debug(f"Streamer version {self.streamer_version}")
		self._debug(f"Signature length {signature_length}")
		
		if self.streamer_version < STREAMER_VERSION_OLD_NEXTSTEP or self.streamer_version > STREAMER_VERSION_CURRENT:
			raise InvalidTypedStreamError(f"Invalid streamer version: {self.streamer_version}")
		elif self.streamer_version == STREAMER_VERSION_OLD_NEXTSTEP:
			raise InvalidTypedStreamError(f"Old NeXTSTEP streamer version ({self.streamer_version}) not supported (yet?)")
		
		if signature_length != SIGNATURE_LENGTH:
			raise InvalidTypedStreamError(f"The signature string must be exactly {SIGNATURE_LENGTH} bytes long, not {signature_length}")
		
		signature = self._read_exact(signature_length)
		self._debug(f"Signature {signature!r}")
		try:
			self.byte_order = _SIGNATURE_TO_ENDIANNESS_MAP[signature]
		except KeyError:
			raise InvalidTypedStreamError(f"Invalid signature string: {signature!r}")
		self._debug(f"\t=> byte order {self.byte_order}")
		
		self.system_version = self._read_integer(signed=False)
		self._debug(f"System version {self.system_version}")
	
	def _read_float(self, head: typing.Optional[int] = None) -> float:
		"""Read a low-level single-precision float value.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The decoded float value.
		"""
		
		self._debug("Single-precision float number")
		head = self._read_head_byte(head)
		if head == TAG_FLOATING_POINT:
			struc = _FLOAT_STRUCTS_BY_BYTE_ORDER[self.byte_order]
			(v,) = struc.unpack(self._read_exact(struc.size))
			return v
		else:
			return float(self._read_integer(head, signed=True))
	
	def _read_double(self, head: typing.Optional[int] = None) -> float:
		"""Read a low-level double-precision float value.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The decoded double value.
		"""
		
		self._debug("Double-precision float number")
		head = self._read_head_byte(head)
		if head == TAG_FLOATING_POINT:
			struc = _DOUBLE_STRUCTS_BY_BYTE_ORDER[self.byte_order]
			(v,) = struc.unpack(self._read_exact(struc.size))
			return v
		else:
			return float(self._read_integer(head, signed=True))
	
	def _read_unshared_string(self, head: typing.Optional[int] = None) -> typing.Optional[bytes]:
		"""Read a low-level string value.
		
		Strings in typedstreams have no specificed encoding,
		so the string data is returned as raw :class:`bytes`.
		(In practice, they usually consist of printable ASCII characters.)
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read string data, which may be ``nil``/``None``.
		"""
		
		self._debug("Unshared string")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		else:
			length = self._read_integer(head, signed=False)
			self._debug(f"\t... length {length}")
			contents = self._read_exact(length)
			self._debug(f"\t... contents {contents!r}")
			return contents
	
	def _read_shared_string(self, head: typing.Optional[int] = None) -> typing.Optional[bytes]:
		"""Read a low-level shared string value.
		
		A shared string value may either be stored literally (as an unshared string)
		or as a reference to a previous literally stored shared string.
		Literal shared strings are appended to the :attr:`shared_string_table` after they are read,
		so that they can be referenced by later non-literal shared strings.
		This happens transparently to the caller -
		in both cases the actual string data is returned.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read string data, which may be ``nil``/``None``.
		"""
		
		self._debug("Shared string")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			string = self._read_unshared_string()
			if string is None:
				raise InvalidTypedStreamError("Literal shared string cannot contain a nil unshared string")
			self._debug(f"\t... {len(self.shared_string_table)} ~ {string!r}")
			self.shared_string_table.append(string)
			return string
		else:
			self._debug("\t... reference")
			reference_number = self._read_integer(head, signed=True)
			decoded = _decode_reference_number(reference_number)
			self._debug(f"\t... number {decoded}")
			string = self.shared_string_table[decoded]
			self._debug(f"\t~ {string!r}")
			return string
	
	def _read_object_reference(self, referenced_type: ObjectReference.Type, head: typing.Optional[int] = None) -> ObjectReference:
		"""Read an object reference value.
		
		Despite the name,
		object references can't just refer to objects,
		but also to classes or C strings.
		The type of object that a reference refers to is always clear from context
		and is not explicitly stored in the typedstream.
		
		:param referenced_type: The type of object that the reference refers to.
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read object reference.
		"""
		
		self._debug(f"Reference to {referenced_type.value}")
		reference_number = self._read_integer(head, signed=True)
		self._debug(f"... number {reference_number}")
		decoded = _decode_reference_number(reference_number)
		self._debug(f"... decoded to {decoded}")
		return ObjectReference(referenced_type, decoded)
	
	def _read_c_string(self, head: typing.Optional[int] = None) -> typing.Optional[typing.Union[CString, ObjectReference]]:
		"""Read a C string value.
		
		A C string value may either be stored literally
		or as a reference to a previous literally stored C string value.
		Literal C string values are returned as :class:`CString` objects.
		C string values stored as references are returned as :class:`ObjectReference` objects
		and are not automatically dereferenced.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read C string value or reference, which may be ``nil``/``None``.
		"""
		
		self._debug("C string")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			string = self._read_shared_string()
			if string is None:
				raise InvalidTypedStreamError("Literal C string cannot contain a nil shared string")
			# The typedstream format does not prevent C strings from containing zero bytes,
			# though the NeXTSTEP/Apple writer never produces such strings,
			# and the reader does not handle them properly.
			if 0 in string:
				raise InvalidTypedStreamError("C string value cannot contain zero bytes")
			return CString(string)
		else:
			self._debug("\t... reference")
			return self._read_object_reference(ObjectReference.Type.C_STRING, head)
	
	def _read_class(self, head: typing.Optional[int] = None) -> typing.Iterable[typing.Optional[typing.Union[SingleClass, ObjectReference]]]:
		"""Iteratively read a class object from the typedstream.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: An iterable of events representing the class object.
			See :class:`SingleClass` for information about what events are generated when and what they mean.
		"""
		
		self._debug("Class")
		head = self._read_head_byte(head)
		while head == TAG_NEW:
			self._debug("\t... new")
			name = self._read_shared_string()
			if name is None:
				raise InvalidTypedStreamError("Class name cannot be nil")
			self._debug(f"\t... name {name!r}")
			version = self._read_integer(signed=True)
			self._debug(f"\t... version {version}")
			yield SingleClass(name, version)
			head = self._read_head_byte()
		
		if head == TAG_NIL:
			self._debug("\t... nil")
			yield None
		else:
			self._debug("\t... reference")
			yield self._read_object_reference(ObjectReference.Type.CLASS, head)
	
	def _read_object(self, head: typing.Optional[int] = None) -> typing.Iterable[ReadEvent]:
		"""Iteratively read an object from the typedstream,
		including all of its contents and the end of object marker.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: An iterable of events representing the object.
			See :class:`BeginObject` and :class:`EndObject` for information about what events are generated when and what they mean.
		"""
		
		self._debug("Object")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			yield None
		elif head == TAG_NEW:
			self._debug("\t... new")
			yield BeginObject()
			yield from self._read_class()
			next_head = self._read_head_byte()
			while next_head != TAG_END_OF_OBJECT:
				yield from self._read_typed_values(next_head)
				next_head = self._read_head_byte()
			yield EndObject()
		else:
			self._debug("\t... reference")
			yield self._read_object_reference(ObjectReference.Type.OBJECT, head)
	
	def _read_value_with_encoding(self, type_encoding: bytes, head: typing.Optional[int] = None) -> typing.Iterable[ReadEvent]:
		"""Iteratively read a single value with the type indicated by the given type encoding.
		
		The type encoding string must contain exactly one type
		(although it may be a compound type like a struct or array).
		Type encoding strings that might contain more than one value must first be split using :func:`_split_encodings`.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: An iterable of events representing the object.
			Simple values are represented by single events,
			but more complex values (classes, objects, arrays, structs) usually generate multiple events.
		"""
		
		self._debug(f"Value with type encoding {type_encoding!r}")
		
		# Unlike other integer types,
		# chars are always stored literally -
		# the usual tags do not apply.
		if type_encoding == b"C":
			yield int.from_bytes(self._read_exact(1), self.byte_order, signed=False)
		elif type_encoding == b"c":
			yield int.from_bytes(self._read_exact(1), self.byte_order, signed=True)
		elif type_encoding in b"SILQ":
			yield self._read_integer(head, signed=False)
		elif type_encoding in b"silq":
			yield self._read_integer(head, signed=True)
		elif type_encoding == b"f":
			yield self._read_float(head)
		elif type_encoding == b"d":
			yield self._read_double(head)
		elif type_encoding == b"*":
			yield self._read_c_string(head)
		elif type_encoding == b":":
			yield Selector(self._read_shared_string(head))
		elif type_encoding == b"+":
			yield self._read_unshared_string(head)
		elif type_encoding == b"#":
			yield from self._read_class(head)
		elif type_encoding == b"@":
			yield from self._read_object(head)
		elif type_encoding.startswith(b"["):
			if not type_encoding.endswith(b"]"):
				raise InvalidTypedStreamError(f"Missing closing bracket in array type encoding {type_encoding!r}")
			
			i = 1
			while i < len(type_encoding) - 1:
				if type_encoding[i] not in b"0123456789":
					break
				i += 1
			length_string, element_type_encoding = type_encoding[1:i], type_encoding[i:-1]
			
			if not length_string:
				raise InvalidTypedStreamError(f"Missing length in array type encoding: {type_encoding!r}")
			if not element_type_encoding:
				raise InvalidTypedStreamError(f"Missing element type in array type encoding: {type_encoding!r}")
			
			length = int(length_string.decode("ascii"))
			
			if element_type_encoding in b"Cc":
				# Special case for byte arrays for faster reading and a better parsed representation.
				yield ByteArray(element_type_encoding, self._read_exact(length))
			else:
				yield BeginArray(element_type_encoding, length)
				for _ in range(length):
					yield from self._read_value_with_encoding(element_type_encoding)
				yield EndArray()
		elif type_encoding.startswith(b"{"):
			if not type_encoding.endswith(b"}"):
				raise InvalidTypedStreamError(f"Missing closing brace in struct type encoding {type_encoding!r}")
			
			try:
				equals_pos = type_encoding.index(b"=")
			except ValueError:
				raise InvalidTypedStreamError(f"Missing name in struct type encoding {type_encoding!r}")
			
			name = type_encoding[1:equals_pos]
			field_type_encodings = list(_split_encodings(type_encoding[equals_pos+1:-1]))
			yield BeginStruct(name, field_type_encodings)
			for field_type_encoding in field_type_encodings:
				yield from self._read_value_with_encoding(field_type_encoding)
			yield EndStruct()
		else:
			raise InvalidTypedStreamError(f"Don't know how to read a value with type encoding {type_encoding!r}")
	
	def _read_typed_values(self, head: typing.Optional[int] = None, *, end_of_stream_ok: bool = False) -> typing.Iterable[ReadEvent]:
		"""Iteratively read the next group of typed values from the stream.
		
		The type encoding string is decoded to determine the type of the following values.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:param end_of_stream_ok: Whether reaching the end of the data stream is an acceptable condition.
			If this method is called when the end of the stream is reached,
			an :class:`EOFError` is raised if this parameter is true,
			and an :class:`InvalidTypedStreamError` is raised if it is false.
			If the end of the stream is reached in the middle of reading a value
			(not right at the beginning),
			the exception is always an :class:`InvalidTypedStreamError`,
			regardless of the value of this parameter.
		:return: An iterable of events representing the typed values.
			See :class:`BeginTypedValues` and :class:`EndTypedValues` for information about what events are generated when and what they mean.
		"""
		
		self._debug("Type encoding-prefixed value")
		
		try:
			head = self._read_head_byte(head)
		except InvalidTypedStreamError:
			if end_of_stream_ok:
				raise EOFError(type(self)._EOF_MESSAGE)
			else:
				raise
		
		encoding_string = self._read_shared_string(head)
		if encoding_string is None:
			raise InvalidTypedStreamError("Encountered nil type encoding string")
		elif not encoding_string:
			raise InvalidTypedStreamError("Encountered empty type encoding string")
		
		encodings = list(_split_encodings(encoding_string))
		yield BeginTypedValues(encodings)
		for encoding in encodings:
			yield from self._read_value_with_encoding(encoding)
		yield EndTypedValues()
	
	def _read_all_values(self) -> typing.Iterator[ReadEvent]:
		"""Iteratively read all values in the typedstream.
		
		:return: An iterable of events representing the contents of the typedstream.
			Top-level values in a typedstream are always prefixed with a type encoding.
			See :class:`BeginTypedValues` and :class:`EndTypedValues` for information about what events are generated when and what they mean.
		"""
		
		while True:
			try:
				yield from self._read_typed_values(end_of_stream_ok=True)
			except EOFError as e:
				# Make sure that the EOFError actually came from our code and not from some other IO code.
				if tuple(e.args) == (type(self)._EOF_MESSAGE,):
					return
				else:
					raise

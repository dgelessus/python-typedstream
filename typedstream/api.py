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


_T = typing.TypeVar("_T")


class TypedValue(typing.Generic[_T]):
	"""Wrapper for an arbitrary value with an attached type encoding."""
	
	encoding: bytes
	value: _T
	
	def __init__(self, encoding: bytes, value: _T) -> None:
		super().__init__()
		
		self.encoding = encoding
		self.value = value
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(type_encoding={self.encoding!r}, value={self.value!r})"
	
	def __str__(self) -> str:
		return f"type {self.encoding!r}: {self.value}"


class ObjectReference(object):
	"""A reference to a previously read object."""
	
	number: int
	
	def __init__(self, number: int) -> None:
		super().__init__()
		
		self.number = number
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}({self.number!r})"
	
	def __str__(self) -> str:
		return f"<reference to object #{self.number}>"


class Group(object):
	"""Representation of a group of values packed together in a typedstream.
	
	This is a thin wrapper around a list,
	to distinguish value groups from arrays
	(which are represented as plain lists).
	
	Value groups in a typedstream are created by serializing multiple values with a single call to ``-[NSArchiver encodeValuesOfObjCTypes:]``.
	This produces different serialized data than calling ``-[NSArchiver encodeValueOfObjCType:at:]`` separately for each of the values.
	The former serializes all values' type encodings joined together into a single string,
	followed by all of the values one immediately after another.
	The latter serializes each value as a separate encoding/value pair.
	
	A :class:`Group` instance returned by :class:`TypedStreamReader` always contains at least two values.
	Single values are returned directly and not wrapped in a :class:`Group` object.
	Empty groups are technically supported by the typedstream format,
	but :class:`TypedStreamReader` treats them as an error,
	as they are never used in practice.
	"""
	
	values: typing.List[TypedValue[typing.Any]]
	
	def __init__(self, values: typing.List[TypedValue[typing.Any]]) -> None:
		super().__init__()
		
		self.values = values
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(values={self.values!r})"
	
	def __str__(self) -> str:
		rep = "group:\n"
		for value in self.values:
			for line in str(value).splitlines():
				rep += "\t" + line + "\n"
		return rep


class Struct(object):
	"""Representation of the contents of a C struct as it is stored in a typedstream.
	
	This is a thin wrapper around a list,
	to distinguish structs from arrays
	(which are represented as plain lists).
	"""
	
	fields: typing.List[TypedValue[typing.Any]]
	
	def __init__(self, fields: typing.List[TypedValue[typing.Any]]) -> None:
		super().__init__()
		
		self.fields = fields
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(fields={self.fields!r})"
	
	def __str__(self) -> str:
		rep = "struct:\n"
		for field_value in self.fields:
			for line in str(field_value).splitlines():
				rep += "\t" + line + "\n"
		return rep


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


class ReferenceNumberedObject(object):
	"""Base class for objects that are assigned a reference number and stored in the shared object table."""
	
	number: int
	
	def __init__(self, number: int) -> None:
		super().__init__()
		
		self.number = number
	
	def __repr__(self) -> str:
		return f"<{type(self).__module__}.{type(self).__qualname__} #{self.number!r} at {id(self):#x}>"


class CString(ReferenceNumberedObject):
	"""Information about a C string as it is stored in a typedstream.
	
	This is a thin wrapper around a plain :class:`bytes` object.
	The wrapper class is used to distinguish typed C string values from untyped bytes.
	"""
	
	contents: bytes
	
	def __init__(self, number: int, contents: bytes) -> None:
		super().__init__(number)
		
		self.contents = contents
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(number={self.number!r}, contents={self.contents!r})"
	
	def __str__(self) -> str:
		return f"(#{self.number}) {self.contents!r}"


class Class(ReferenceNumberedObject):
	"""Information about a class as it is stored at the start of objects in a typedstream."""
	
	name: bytes
	version: int
	superclass: typing.Optional[typing.Union["Class", ObjectReference]]
	
	def __init__(self, number: int, name: bytes, version: int, superclass: typing.Optional[typing.Union["Class", ObjectReference]]) -> None:
		super().__init__(number)
		
		self.name = name
		self.version = version
		self.superclass = superclass
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(number={self.number!r}, name={self.name!r}, version={self.version!r}, superclass={self.superclass!r})"
	
	def __str__(self) -> str:
		rep = f"(#{self.number}) {self.name.decode('ascii', errors='backslashreplace')} v{self.version}"
		if self.superclass is not None:
			rep += f", extends {self.superclass}"
		return rep


# Placeholder value for class fields that have not been initialized yet.
# This is needed because classes and objects have to be inserted into the shared_object_table
# before their superclass/class fields can be set.
CLASS_NOT_SET_YET = Class(-1, b"<placeholder - class has not been read/set yet>", -1, None)


class Object(ReferenceNumberedObject):
	"""Representation of an object as it is stored in a typedstream.
	
	Currently this is only used as a placeholder for the object in the :attr:`TypedStreamReader.shared_object_table`
	to make the reference numbering work as required.
	"""
	
	clazz: typing.Union[Class, ObjectReference]
	contents: typing.List[TypedValue[typing.Any]]
	
	def __init__(self, number: int, clazz: typing.Union[Class, ObjectReference], contents: typing.List[TypedValue[typing.Any]]) -> None:
		super().__init__(number)
		
		self.clazz = clazz
		self.contents = contents
	
	def __repr__(self) -> str:
		return f"{type(self).__module__}.{type(self).__qualname__}(number={self.number!r}, clazz={self.clazz!r}, contents={self.contents!r})"
	
	def __str__(self) -> str:
		rep = f"object (#{self.number}) of class {self.clazz}, "
		if not self.contents:
			rep += "no contents"
		else:
			rep += "contents:\n"
			for value in self.contents:
				for line in str(value).splitlines():
					rep += "\t" + line + "\n"
		return rep


class TypedStreamReader(typing.ContextManager["TypedStreamReader"]):
	"""Reads typedstream data from a raw byte stream."""
	
	_EOF_MESSAGE: typing.ClassVar[str] = "End of typedstream reached"
	
	_is_debug_on: bool
	_close_stream: bool
	_stream: typing.BinaryIO
	
	shared_string_table: typing.List[bytes]
	shared_object_table: typing.List[ReferenceNumberedObject]
	
	streamer_version: int
	byte_order: str
	system_version: int
	
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
		self.shared_object_table = []
		
		try:
			self._read_header()
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
	
	def _read_object_reference(self, head: typing.Optional[int] = None) -> ObjectReference:
		"""
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read object reference.
		"""
		
		self._debug("Object reference")
		reference_number = self._read_integer(head, signed=True)
		self._debug(f"... number {reference_number}")
		decoded = _decode_reference_number(reference_number)
		self._debug(f"... decoded to {decoded}")
		return ObjectReference(decoded)
	
	def _read_c_string(self, head: typing.Optional[int] = None) -> typing.Optional[typing.Union[CString, ObjectReference]]:
		"""Read a C string value.
		
		A C string value may either be stored literally
		or as a reference to a previous literally stored C string value.
		Literal C string values are appended to the :attr:`shared_object_table` as they are being read.
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
			cstring = CString(len(self.shared_object_table), string)
			self._debug(f"\t... {cstring}")
			self.shared_object_table.append(cstring)
			return cstring
		else:
			self._debug("\t... reference")
			return self._read_object_reference(head)
	
	def _read_class(self, head: typing.Optional[int] = None) -> typing.Optional[typing.Union[Class, ObjectReference]]:
		"""Read a class object.
		
		Class objects are only found at the start of an object (indicating the object's class),
		or at the end of another class object (indicating the class's superclass).
		
		A class object may either be stored literally
		or as a reference to a previous literally stored class object.
		Literal class objects are appended to the :attr:`shared_object_table` as they are being read.
		Class objects stored as references are returned as :class:`ObjectReference` objects
		and are not automatically dereferenced.
		
		Because of how the typedstream format expects references to be numbered,
		classes are already added to :attr:`shared_object_table` before they are fully initialized.
		Class objects in this state have their :attr:`~Class.superclass` attribute set to the special value :attr:`CLASS_NOT_SET_YET`.
		This state usually isn't visible to callers though -
		once the class object is returned,
		it is fully initialized.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read class object or reference, which may be ``Nil``/``None``.
		"""
		
		self._debug("Class")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			name = self._read_shared_string()
			if name is None:
				raise InvalidTypedStreamError("Class name cannot be nil")
			self._debug(f"\t... name {name!r}")
			version = self._read_integer(signed=True)
			self._debug(f"\t... version {version}")
			clazz = Class(len(self.shared_object_table), name, version, CLASS_NOT_SET_YET)
			self._debug(f"\t... {clazz}")
			self.shared_object_table.append(clazz)
			# This recurses until nil (no superclass) or a reference to a previous class is found.
			superclass = self._read_class()
			self._debug(f"\t... superclass {superclass}")
			clazz.superclass = superclass
			return clazz
		else:
			self._debug("\t... reference")
			return self._read_object_reference(head)
	
	def _read_object_start(self, head: typing.Optional[int] = None) -> typing.Optional[typing.Union[Object, ObjectReference]]:
		"""Read the start of an object,
		i. e. its class information.
		
		An object may either be stored literally
		or as a reference to a previous literally stored object.
		Literal objects are appended to the :attr:`shared_object_table` as they are being read.
		Objects stored as references are returned as :class:`ObjectReference` objects
		and are not automatically dereferenced.
		
		If the return value is an :class:`Object`,
		the object is stored literally.
		The caller is expected to read the object's data
		that follows the start of the object
		and store it in the object's :attr:`~Object.contents` attribute,
		until the matching end of object tag is reached.
		
		If the return value is ``None`` or an :class:`ObjectReference`,
		there is no following object data or end of object tag that need to be read by the caller.
		
		Because of how the typedstream format expects references to be numbered,
		objects are already added to :attr:`shared_object_table` before they are fully initialized.
		Objects in this state have their :attr:`~Object.clazz` attribute set to the special value :attr:`CLASS_NOT_SET_YET`.
		This state usually isn't visible to callers though -
		once the object is returned,
		it is fully initialized.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read object or reference, which may be ``nil``/``None``.
		"""
		
		self._debug("Object")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			obj = Object(len(self.shared_object_table), CLASS_NOT_SET_YET, [])
			self._debug(f"\t... {obj}")
			self.shared_object_table.append(obj)
			clazz = self._read_class()
			self._debug(f"\t... of class {clazz}")
			if clazz is None:
				raise InvalidTypedStreamError("Object class cannot be nil")
			obj.clazz = clazz
			return obj
		else:
			self._debug("\t... reference")
			return self._read_object_reference(head)
	
	def _read_value_with_encoding(self, type_encoding: bytes, head: typing.Optional[int] = None) -> typing.Any:
		"""Read a single value with the type indicated by the given type encoding.
		
		The type encoding string must contain exactly one type
		(although it may be a compound type like a struct or array).
		Type encoding strings that might contain more than one value must first be split using :func:`_split_encodings`.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read value, converted to a Python representation.
		"""
		
		self._debug(f"Value with type encoding {type_encoding!r}")
		
		# Unlike other integer types,
		# chars are always stored literally -
		# the usual tags do not apply.
		if type_encoding == b"C":
			return int.from_bytes(self._read_exact(1), self.byte_order, signed=False)
		elif type_encoding == b"c":
			return int.from_bytes(self._read_exact(1), self.byte_order, signed=True)
		elif type_encoding in b"SILQ":
			return self._read_integer(head, signed=False)
		elif type_encoding in b"silq":
			return self._read_integer(head, signed=True)
		elif type_encoding == b"f":
			return self._read_float(head)
		elif type_encoding == b"d":
			return self._read_double(head)
		elif type_encoding == b"*":
			return self._read_c_string(head)
		elif type_encoding == b":":
			return Selector(self._read_shared_string(head))
		elif type_encoding == b"+":
			return self._read_unshared_string(head)
		elif type_encoding == b"#":
			return self._read_class(head)
		elif type_encoding == b"@":
			obj = self._read_object_start(head)
			if isinstance(obj, Object):
				# Object is stored literally and is not nil or a reference,
				# so read the contents until the end of the object is reached.
				next_head = self._read_head_byte()
				while next_head != TAG_END_OF_OBJECT:
					obj.contents.append(self.read_value(next_head))
					next_head = self._read_head_byte()
			return obj
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
				return self._read_exact(length)
			else:
				return [self._read_value_with_encoding(element_type_encoding) for _ in range(length)]
		elif type_encoding.startswith(b"{"):
			if not type_encoding.endswith(b"}"):
				raise InvalidTypedStreamError(f"Missing closing brace in struct type encoding {type_encoding!r}")
			
			try:
				equals_pos = type_encoding.index(b"=")
			except ValueError:
				raise InvalidTypedStreamError(f"Missing name in struct type encoding {type_encoding!r}")
			
			field_type_encodings = type_encoding[equals_pos+1:-1]
			return Struct([
				TypedValue(field_type_encoding, self._read_value_with_encoding(field_type_encoding))
				for field_type_encoding in _split_encodings(field_type_encodings)
			])
		else:
			raise InvalidTypedStreamError(f"Don't know how to read a value with type encoding {type_encoding!r}")
	
	def read_value(self, head: typing.Optional[int] = None, *, end_of_stream_ok: bool = False) -> TypedValue[typing.Any]:
		"""Read the next typed value from the stream,
		which may have any type (primitive or object).
		
		The type encoding string is decoded to determine the type of the following value,
		which is then read and converted to a Python representation.
		
		If the type encoding string contains more than one type,
		all of the corresponding values are read and returned as a :class:`Group`.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:param end_of_stream_ok: Whether reaching the end of the data stream is an acceptable condition.
			If this method is called when the end of the stream is reached,
			an :class:`EOFError` is raised if this parameter is true,
			and an :class:`InvalidTypedStreamError` is raised if it is false.
			If the end of the stream is reached in the middle of reading a value
			(not right at the beginning),
			the exception is always an :class:`InvalidTypedStreamError`,
			regardless of the value of this parameter.
		:return: The read value and its type encoding.
		"""
		
		self._debug("Type encoding-prefixed value")
		
		try:
			head = self._read_head_byte(head)
		except InvalidTypedStreamError:
			if end_of_stream_ok:
				raise EOFError(type(self)._EOF_MESSAGE)
			else:
				raise
		
		encodings = self._read_shared_string(head)
		if encodings is None:
			raise InvalidTypedStreamError("Encountered nil type encoding string")
		elif not encodings:
			raise InvalidTypedStreamError("Encountered empty type encoding string")
		
		values = [
			TypedValue(encoding, self._read_value_with_encoding(encoding))
			for encoding in _split_encodings(encodings)
		]
		assert values
		if len(values) == 1:
			(value,) = values
			assert value.encoding == encodings
			return value
		else:
			return TypedValue(encodings, Group(values))
	
	@property
	def values(self) -> typing.Iterator[TypedValue[typing.Any]]:
		"""Iterator over the typed values stored in the stream.
		
		Iterating over :attr:`values` is equivalent to repeatedly calling :func:`read_value` until the end of the stream is reached.
		"""
		
		while True:
			try:
				yield self.read_value(end_of_stream_ok=True)
			except EOFError as e:
				# Make sure that the EOFError actually came from our code and not from some other IO code.
				if tuple(e.args) == (type(self)._EOF_MESSAGE,):
					return
				else:
					raise

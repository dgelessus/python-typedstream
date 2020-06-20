import abc
import os
import types
import typing


__version__ = "0.0.1.dev"

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
TAG_INTEGER_2 = 0x81
# Indicates an integer value, stored in 4 bytes.
TAG_INTEGER_4 = 0x82
# Indicates a floating-point value, stored in 4 or 8 bytes (depending on whether it is a float or a double).
TAG_FLOATING_POINT = 0x83
# Indicates the start of a string value or an object that is stored literally and not as a backreference.
TAG_NEW = 0x84
# Indicates a nil value. Used for strings (unshared and shared), classes, and objects.
TAG_NIL = 0x85
# Indicates the end of an object.
TAG_END_OF_OBJECT = 0x86

# The lowest and highest values reserved for use as tags.
# Values outside this range are used to literally encode single-byte integers.
# Integer values that fall into the tag range must be encoded in two separate bytes using TAG_INTEGER_2
# so that they do not conflict with the tags.
FIRST_TAG = 0x80
LAST_TAG = 0x91
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
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


class TypedStreamObjectBase(abc.ABC):
	"""Abstract base class for objects that can appear in :attr:`TypedStreamReader.shared_object_table`."""


class Class(TypedStreamObjectBase):
	"""Information about a class as it is stored at the start of objects in a typedstream."""
	
	name: bytes
	version: int
	superclass: typing.Optional["Class"]
	
	def __init__(self, name: bytes, version: int, superclass: typing.Optional["Class"]) -> None:
		super().__init__()
		
		self.name = name
		self.version = version
		self.superclass = superclass
	
	def __repr__(self):
		return f"{type(self).__module__}.{type(self).__qualname__}(name={self.name!r}, version={self.version!r}, superclass={self.superclass!r})"
	
	def __str__(self):
		rep = f"{self.name.decode('ascii', errors='backslashreplace')} v{self.version}"
		if self.superclass is not None:
			rep += f", extends {self.superclass}"
		return rep


# Placeholder value for class fields that have not been initialized yet.
# This is needed because classes and objects have to be inserted into the shared_object_table
# before their superclass/class fields can be set.
CLASS_NOT_SET_YET = Class(b"<placeholder - class has not been read/set yet>", -1, None)


class Object(TypedStreamObjectBase):
	"""Representation of an object as it is stored in a typedstream.
	
	Currently this is only used as a placeholder for the object in the :attr:`TypedStreamReader.shared_object_table`
	to make the reference numbering work as required.
	"""
	
	clazz: Class
	
	finished: bool
	
	def __init__(self, clazz: Class, finished: bool) -> None:
		super().__init__()
		
		self.clazz = clazz
		self.finished = finished
	
	def __repr__(self):
		return f"{type(self).__module__}.{type(self).__qualname__}(clazz={self.clazz!r}, finished={self.finished!r})"
	
	def __str__(self):
		rep = f"object "
		if not self.finished:
			rep += "(unfinished) "
		rep += f"of class {self.clazz}"
		return rep


class TypedStreamReader(typing.ContextManager["TypedStreamReader"]):
	"""Reads typedstream data from a raw byte stream."""
	
	_is_debug_on: bool
	_close_stream: bool
	_stream: typing.BinaryIO
	
	shared_string_table: typing.List[bytes]
	shared_object_table: typing.List[TypedStreamObjectBase]
	
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
	
	def __repr__(self):
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
			(head,) = self._read_exact(1)
			self._debug(f"Head byte: {head} ({head:#x})")
		return head
	
	def _read_integer(self, head: typing.Optional[int] = None) -> int:
		"""Read a low-level integer value.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The decoded integer value.
		"""
		
		self._debug(f"Standalone integer")
		head = self._read_head_byte(head)
		if head not in TAG_RANGE:
			self._debug(f"\t... literal integer in head: {head} ({head:#x})")
			return head
		elif head == TAG_INTEGER_2:
			v = int.from_bytes(self._read_exact(2), self.byte_order)
			self._debug(f"\t... literal integer in 2 bytes: {v} ({v:#x})")
			return v
		elif head == TAG_INTEGER_4:
			v = int.from_bytes(self._read_exact(4), self.byte_order)
			self._debug(f"\t... literal integer in 4 bytes: {v} ({v:#x})")
			return v
		else:
			raise InvalidTypedStreamError(f"Invalid head tag in this context: 0x{head:>02x}")
	
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
		self._debug(f"Signature {signature}")
		try:
			self.byte_order = _SIGNATURE_TO_ENDIANNESS_MAP[signature]
		except KeyError:
			raise InvalidTypedStreamError(f"Invalid signature string: {signature}")
		self._debug(f"\t=> byte order {self.byte_order}")
		
		self.system_version = self._read_integer()
		self._debug(f"System version {self.system_version}")
	
	def _read_unshared_string(self, head: typing.Optional[int] = None) -> typing.Optional[bytes]:
		"""Read a low-level string value.
		
		Strings in typedstreams have no specificed encoding,
		so the string data is returned as raw :class:`bytes`.
		(In practice, they usually consist of printable ASCII characters.)
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The read string data, which may be ``nil``/``None``.
		"""
		
		self._debug(f"Unshared string")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		else:
			length = self._read_integer(head)
			self._debug(f"\t... length {length}")
			contents = self._read_exact(length)
			self._debug(f"\t... contents {contents}")
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
		
		self._debug(f"Shared string")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			string = self._read_unshared_string()
			assert string is not None
			self._debug(f"\t... {len(self.shared_string_table)} ~ {string}")
			self.shared_string_table.append(string)
			return string
		else:
			self._debug("\t... reference")
			reference_number = self._read_integer(head)
			decoded = _decode_reference_number(reference_number)
			self._debug(f"\t... number {decoded}")
			string = self.shared_string_table[decoded]
			self._debug(f"\t~ {string}")
			return string
	
	def _read_class(self, head: typing.Optional[int] = None) -> typing.Optional[Class]:
		"""Read a class object.
		
		Class objects are only found at the start of an object (indicating the object's class),
		or at the end of another class object (indicating the class's superclass).
		
		A class object may either be stored literally
		or as a reference to a previous literally stored class object.
		Literal class objects are appended to the :attr:`shared_object_table` as they are being read,
		so that they can be referenced by later non-literal class objects.
		This happens transparently to the caller -
		in both cases the actual class object is returned.
		
		Because of how the typedstream format expects references to be numbered,
		classes are already added to :attr:`shared_object_table` before they are fully initialized.
		Class objects in this state have their :attr:`~Class.superclass` attribute set to the special value :attr:`CLASS_NOT_SET_YET`.
		This state usually isn't visible to callers though -
		once the class object is returned,
		it is fully initialized.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The fully decoded class object, which may be ``Nil``/``None``.
		"""
		
		self._debug(f"Class")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			name = self._read_shared_string()
			self._debug(f"\t... name {name}")
			version = self._read_integer()
			self._debug(f"\t... version {version}")
			clazz = Class(name, version, CLASS_NOT_SET_YET)
			self._debug(f"\t... {len(self.shared_object_table)} ~ {clazz}")
			self.shared_object_table.append(clazz)
			# This recurses until nil (no superclass) or a reference to a previous class is found.
			superclass = self._read_class()
			self._debug(f"\t... superclass {superclass}")
			clazz.superclass = superclass
			return clazz
		else:
			self._debug("\t... reference")
			reference_number = self._read_integer(head)
			decoded = _decode_reference_number(reference_number)
			self._debug(f"\t... number {decoded}")
			clazz = self.shared_object_table[decoded]
			self._debug(f"\t~ {clazz}")
			if not isinstance(clazz, Class):
				raise InvalidTypedStreamError(f"Expected reference to a Class, not {type(clazz)}")
			return clazz
	
	def _read_object_start(self, head: typing.Optional[int] = None) -> typing.Optional[Object]:
		"""Read the start of an object,
		i. e. its class information.
		
		An object may either be stored literally
		or as a reference to a previous literally stored object.
		Literal objects are appended to the :attr:`shared_object_table` as they are being read,
		so that they can be referenced by later non-literal objects.
		In both cases an object value is returned,
		although the two cases need to be handled differently by the caller.
		
		If the object's :attr:`~Object.finished` attribute is false,
		the object is stored literally.
		The caller is expected to read the object's data
		that follows the start of the object
		until the matching end of object tag is reached
		and then set :attr:`~Object.finished` to ``True``.
		
		If :attr:`~Object.finished` is already true when the object is returned,
		the object was a reference to a previous literally stored object.
		In this case there is no following object data or end of object tag that need to be read.
		
		Because of how the typedstream format expects references to be numbered,
		objects are already added to :attr:`shared_object_table` before they are fully initialized.
		Objects in this state have their :attr:`~Object.clazz` attribute set to the special value :attr:`CLASS_NOT_SET_YET`.
		This state usually isn't visible to callers though -
		once the object is returned,
		it is fully initialized.
		
		:param head: An already read head byte to use, or ``None`` if the head byte should be read from the stream.
		:return: The (possibly not read yet) object, which may be ``Nil``/``None``.
		"""
		
		self._debug(f"Object")
		head = self._read_head_byte(head)
		if head == TAG_NIL:
			self._debug("\t... nil")
			return None
		elif head == TAG_NEW:
			self._debug("\t... new")
			obj = Object(CLASS_NOT_SET_YET, finished=False)
			self._debug(f"\t... {len(self.shared_object_table)} ~ {obj}")
			self.shared_object_table.append(obj)
			clazz = self._read_class()
			self._debug(f"\t... of class {clazz}")
			if clazz is None:
				raise InvalidTypedStreamError("Object class cannot be nil")
			obj.clazz = clazz
			return obj
		else:
			self._debug("\t... reference")
			reference_number = self._read_integer(head)
			decoded = _decode_reference_number(reference_number)
			self._debug(f"\t... number {decoded}")
			obj = self.shared_object_table[decoded]
			self._debug(f"\t~ {obj}")
			if not isinstance(obj, Object):
				raise InvalidTypedStreamError(f"Expected reference to an Object, not {type(obj)}")
			return obj

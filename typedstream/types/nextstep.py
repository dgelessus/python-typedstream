import collections
import typing

from .. import advanced_repr
from .. import archiver
from . import _common


@archiver.archived_class
class Object(archiver.KnownArchivedObject):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version != 0:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class List(Object, _common.ArraySetBase):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			_, count = unarchiver.decode_values_of_types(b"i", b"i")
			if count < 0:
				raise ValueError(f"List element count cannot be negative: {count}")
			self.elements = list(unarchiver.decode_array(b"@", count).elements)
		elif class_version == 1:
			count = unarchiver.decode_value_of_type(b"i")
			if count < 0:
				raise ValueError(f"List element count cannot be negative: {count}")
			
			if count > 0:
				self.elements = list(unarchiver.decode_array(b"@", count).elements)
			else:
				# If the list is empty,
				# the array isn't stored at all.
				self.elements = []
		else:
			raise ValueError(f"Unsupported version: {class_version}")


@archiver.archived_class
class HashTable(Object, advanced_repr.AsMultilineStringBase):
	contents: "collections.OrderedDict[typing.Any, typing.Any]"
	key_type_encoding: bytes
	value_type_encoding: bytes
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			string_type_encoding = b"*"
		elif class_version == 1:
			string_type_encoding = b"%"
		else:
			raise ValueError(f"Unsupported version: {class_version}")
		
		count, self.key_type_encoding, self.value_type_encoding = unarchiver.decode_values_of_types(b"i", string_type_encoding, string_type_encoding)
		if count < 0:
			raise ValueError(f"HashTable element count cannot be negative: {count}")
		
		self.contents = collections.OrderedDict()
		for _ in range(count):
			key = unarchiver.decode_value_of_type(self.key_type_encoding)
			value = unarchiver.decode_value_of_type(self.value_type_encoding)
			self.contents[key] = value
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.contents:
			count_desc = "empty"
		elif len(self.contents) == 1:
			count_desc = "1 entry:"
		else:
			count_desc = f"{len(self.contents)} entries:"
		
		yield f"{type(self).__name__}, key/value types {self.key_type_encoding!r}/{self.value_type_encoding!r}, {count_desc}"
		
		for key, value in self.contents.items():
			value_it = iter(advanced_repr.as_multiline_string(value, calling_self=self, state=state))
			yield f"\t{key!r}: " + next(value_it, "")
			for line in value_it:
				yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(key_type_encoding={self.key_type_encoding!r}, value_type_encoding={self.value_type_encoding!r}, contents={self.contents!r})"


@archiver.archived_class
class StreamTable(HashTable):
	class _UnarchivedContents(typing.Mapping[typing.Any, typing.Any]):
		archived_contents: typing.Mapping[typing.Any, bytes]
		
		def __init__(self, archived_contents: typing.Mapping[typing.Any, bytes]) -> None:
			super().__init__()
			
			self.archived_contents = archived_contents
		
		def __len__(self) -> int:
			return len(self.archived_contents)
		
		def __iter__(self) -> typing.Iterator[typing.Any]:
			return iter(self.archived_contents)
		
		def keys(self) -> typing.AbstractSet[typing.Any]:
			return self.archived_contents.keys()
		
		def __getitem__(self, key: typing.Any) -> typing.Any:
			return archiver.unarchive_from_data(self.archived_contents[key])
	
	unarchived_contents: "collections.Mapping[typing.Any, typing.Any]"
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 1:
			if self.value_type_encoding != b"!":
				raise ValueError(f"StreamTable values must be ignored, not {self.value_type_encoding!r}")
			
			for key in self.contents:
				assert self.contents[key] is None
				key_again = unarchiver.decode_value_of_type(self.key_type_encoding)
				if key != key_again:
					raise ValueError(f"Expected to read value for key {key}, but found {key_again}")
				self.contents[key] = unarchiver.decode_data_object()
			
			self.unarchived_contents = StreamTable._UnarchivedContents(self.contents)
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.unarchived_contents:
			count_desc = "empty"
		elif len(self.unarchived_contents) == 1:
			count_desc = "1 entry:"
		else:
			count_desc = f"{len(self.unarchived_contents)} entries:"
		
		yield f"{type(self).__name__}, {count_desc}"
		
		for key, value in self.unarchived_contents.items():
			value_it = iter(advanced_repr.as_multiline_string(value, calling_self=self, state=state))
			yield f"\t{key!r}: " + next(value_it, "")
			for line in value_it:
				yield "\t" + line


@archiver.archived_class
class Storage(Object, advanced_repr.AsMultilineStringBase):
	element_type_encoding: bytes
	element_size: int
	elements: typing.List[typing.Any]
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, class_version: int) -> None:
		if class_version == 0:
			self.element_type_encoding, self.element_size, _, count = unarchiver.decode_values_of_types(b"*", b"i", b"i", b"i")
			if count < 0:
				raise ValueError(f"Storage element count cannot be negative: {count}")
			self.elements = list(unarchiver.decode_array(self.element_type_encoding, count).elements)
		elif class_version == 1:
			self.element_type_encoding, self.element_size, count = unarchiver.decode_values_of_types(b"%", b"i", b"i")
			if count < 0:
				raise ValueError(f"Storage element count cannot be negative: {count}")
			
			if count > 0:
				self.elements = list(unarchiver.decode_array(self.element_type_encoding, count).elements)
			else:
				# If the Storage is empty,
				# the array isn't stored at all.
				self.elements = []
		else:
			raise ValueError(f"Unsupported version: {class_version}")
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.elements:
			count_desc = "empty"
		elif len(self.elements) == 1:
			count_desc = "1 element:"
		else:
			count_desc = f"{len(self.elements)} elements:"
		
		yield f"{type(self).__name__}, element type {self.element_type_encoding!r} ({self.element_size!r} bytes each), {count_desc}"
		
		for element in self.elements:
			for line in advanced_repr.as_multiline_string(element, calling_self=self, state=state):
				yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(element_type_encoding={self.element_type_encoding!r}, element_size={self.element_size!r}, elements={self.elements!r})"

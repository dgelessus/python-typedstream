from . import archiver


@archiver.archived_class
class NSObject(archiver.KnownArchivedObject):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, archived_class: archiver.Class) -> None:
		if archived_class.version != 0:
			raise ValueError(f"Unsupported version: {archived_class.version}")


@archiver.archived_class
class NSData(NSObject):
	data: bytes
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, archived_class: archiver.Class) -> None:
		if archived_class.version == 0:
			length = unarchiver.decode_typed_values(b"i")
			self.data = unarchiver.decode_typed_values(f"[{length}c]".encode("ascii"))
		else:
			raise ValueError(f"Unsupported version: {archived_class.version}")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.data!r})"


@archiver.archived_class
class NSMutableData(NSData):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, archived_class: archiver.Class) -> None:
		if archived_class.version != 0:
			raise ValueError(f"Unsupported version: {archived_class.version}")


@archiver.archived_class
class NSString(NSObject):
	value: str
	
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, archived_class: archiver.Class) -> None:
		if archived_class.version == 1:
			self.value = unarchiver.decode_typed_values(b"+").decode("utf-8")
		else:
			raise ValueError(f"Unsupported version: {archived_class.version}")
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.value!r})"


@archiver.archived_class
class NSMutableString(NSString):
	def _init_from_unarchiver_(self, unarchiver: archiver.Unarchiver, archived_class: archiver.Class) -> None:
		if archived_class.version != 1:
			raise ValueError(f"Unsupported version: {archived_class.version}")

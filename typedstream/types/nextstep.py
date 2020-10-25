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

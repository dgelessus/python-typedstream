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
import types
import typing


__all__ = [
	"RecursiveReprState",
	"AsMultilineStringBase",
	"as_multiline_string",
]


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

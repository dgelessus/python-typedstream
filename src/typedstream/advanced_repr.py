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


import contextvars
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


_state: "contextvars.ContextVar[RecursiveReprState]" = contextvars.ContextVar("_state")


class AsMultilineStringBase(object):
	"""Base class for classes that want to implement a custom multiline string representation,
	for use by :func:`as_multiline_string`.
	
	This also provides an implementation of ``__str__`` based on :meth:`~AsMultilineStringBase._as_multiline_string_`.
	"""
	
	detect_backreferences: typing.ClassVar[bool] = True
	
	def _as_multiline_string_header_(self) -> str:
		"""Render the header part of this object's multiline string representation.
		
		The header should be a compact single-line overview description of the object.
		Usually it should indicate the object's type
		and other relevant attributes that can be represented in a short form,
		e. g. the length of a collection.
		
		If the body part is non-empty,
		then the header automatically has a colon appended.
		
		Because the header is always fully rendered even for multiple references to the same object,
		it shouldn't recursively render other complex objects,
		especially ones that might have cyclic references back to this object.
		
		:return: The string representation as an iterable of lines (line terminators not included).
		"""
		
		raise NotImplementedError()
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		"""Render the body part of this object's multiline string representation.
		
		The body is always rendered after the header,
		so it shouldn't duplicate any information that is already part of the header.
		
		Each line in the body is automatically indented by one tab
		so that the body appears visually nested under the header.
		
		:return: The string representation as an iterable of lines (line terminators not included).
		"""
		
		raise NotImplementedError()
	
	def _as_multiline_string_(self) -> typing.Iterable[str]:
		"""Convert ``self`` to a multiline string representation.
		
		This method should not be called directly -
		use :func:`as_multiline_string` instead.
		
		The default implementation is based on :meth:`_as_multiline_string_header_` and :meth:`_as_multiline_string_body_`.
		It first outputs the header on its own line,
		then all of the body lines indented by one tab each.
		If this object has already been rendered before
		(due to multiple or circular references),
		then the body lines are *not* rendered again
		and only the header is output
		(followed by a short explanation).
		
		If the default implementation of this method is overridden,
		then :meth:`_as_multiline_string_header_` and :meth:`_as_multiline_string_body_` don't have to be implemented.
		
		:return: The string representation as an iterable of lines (line terminators not included).
		"""
		
		first = self._as_multiline_string_header_()
		state = _state.get()
		if id(self) in state.currently_rendering_ids:
			yield first + " (circular reference)"
		elif type(self).detect_backreferences and id(self) in state.already_rendered_ids:
			yield first + " (backreference)"
		else:
			body_it = iter(self._as_multiline_string_body_())
			# Silly hack: append the colon to the first line only if at least one more line comes after it.
			try:
				second = next(body_it)
			except StopIteration:
				yield first
			else:
				yield first + ":"
				yield "\t" + second
				for line in body_it:
					yield "\t" + line
	
	def __str__(self) -> str:
		return "\n".join(self._as_multiline_string_())


def as_multiline_string(
	obj: object,
	*,
	calling_self: typing.Optional[object] = None,
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
	:return: The string representation as an iterable of lines (line terminators not included).
	"""
	
	token: typing.Optional[contextvars.Token] = None
	
	try:
		try:
			_state.get()
		except LookupError:
			token = _state.set(RecursiveReprState(set(), []))
		
		if isinstance(obj, AsMultilineStringBase):
			with _state.get()._representing(calling_self):
				yield from obj._as_multiline_string_()
		else:
			yield from str(obj).splitlines()
	finally:
		if token is not None:
			_state.reset(token)

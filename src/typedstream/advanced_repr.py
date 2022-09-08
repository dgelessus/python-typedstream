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
import typing


__all__ = [
	"prefix_lines",
	"AsMultilineStringBase",
	"as_multiline_string",
]


def prefix_lines(
	lines: typing.Iterable[str],
	*,
	first: str = "",
	rest: str = "",
) -> typing.Iterable[str]:
	it = iter(lines)
	
	try:
		yield first + next(it)
	except StopIteration:
		if first:
			yield first
	
	if rest:
		for line in it:
			yield rest + line
	else:
		yield from it


_already_rendered_ids: "contextvars.ContextVar[typing.Set[int]]" = contextvars.ContextVar("_already_rendered_ids")
_currently_rendering_ids: "contextvars.ContextVar[typing.Tuple[int, ...]]" = contextvars.ContextVar("_currently_rendering_ids")


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
		if id(self) in _currently_rendering_ids.get()[:-1]: # last element of _currently_rendering_ids is always id(self)
			yield first + " (circular reference)"
		elif type(self).detect_backreferences and id(self) in _already_rendered_ids.get():
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


def as_multiline_string(obj: object, *, prefix: str = "") -> typing.Iterable[str]:
	"""Convert an object to a multiline string representation.
	
	If the object has an :meth:`~AsMultilineStringBase._as_multiline_string_` method,
	it is used to create the multiline string representation.
	Otherwise,
	the object is converted to a string using default :class:`str` conversion,
	and then split into an iterable of lines.
	
	:param obj: The object to represent.
	:param prefix: An optional prefix to add in front of the first line of the string representation.
		Convenience shortcut for :func:`prefix_lines`.
	:return: The string representation as an iterable of lines (line terminators not included).
	"""
	
	already_rendered_ids: typing.Optional[typing.Set[int]] = None
	token: typing.Optional[contextvars.Token] = None
	token2: typing.Optional[contextvars.Token] = None
	
	try:
		try:
			already_rendered_ids = _already_rendered_ids.get()
		except LookupError:
			already_rendered_ids = set()
			token = _already_rendered_ids.set(already_rendered_ids)
		
		try:
			currently_rendering_ids = _currently_rendering_ids.get()
		except LookupError:
			currently_rendering_ids = ()
		else:
			already_rendered_ids.add(currently_rendering_ids[-1])
		
		token2 = _currently_rendering_ids.set(currently_rendering_ids + (id(obj),))
		
		if isinstance(obj, AsMultilineStringBase):
			res = obj._as_multiline_string_()
		else:
			res = str(obj).splitlines()
		
		yield from prefix_lines(res, first=prefix)
	finally:
		if already_rendered_ids is not None:
			already_rendered_ids.add(id(obj))
		
		if token2 is not None:
			_currently_rendering_ids.reset(token2)
		
		if token is not None:
			_already_rendered_ids.reset(token)

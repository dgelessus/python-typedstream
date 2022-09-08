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


import typing

from .. import advanced_repr


class ArraySetBase(advanced_repr.AsMultilineStringBase):
	detect_backreferences = False
	
	elements: typing.List[typing.Any]
	
	def _as_multiline_string_header_(self) -> str:
		if not self.elements:
			count_desc = "empty"
		elif len(self.elements) == 1:
			count_desc = "1 element"
		else:
			count_desc = f"{len(self.elements)} elements"
		
		return f"{type(self).__name__}, {count_desc}"
	
	def _as_multiline_string_body_(self) -> typing.Iterable[str]:
		for element in self.elements:
			yield from advanced_repr.as_multiline_string(element)
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.elements!r})"

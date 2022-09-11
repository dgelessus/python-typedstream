# This file is part of the python-typedstream library.
# Copyright (C) 2022 dgelessus
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


from .. import archiving


@archiving.struct_class
class CGPoint(archiving.KnownStruct):
	struct_name = b"CGPoint"
	field_encodings = [b"d", b"d"]
	
	x: float
	y: float
	
	def __init__(self, x: float, y: float) -> None:
		super().__init__()
		
		self.x = x
		self.y = y
	
	def __str__(self) -> str:
		x = int(self.x) if int(self.x) == self.x else self.x
		y = int(self.y) if int(self.y) == self.y else self.y
		return f"{{{x}, {y}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(x={self.x!r}, y={self.y!r})"


@archiving.struct_class
class CGSize(archiving.KnownStruct):
	struct_name = b"CGSize"
	field_encodings = [b"d", b"d"]
	
	width: float
	height: float
	
	def __init__(self, width: float, height: float) -> None:
		super().__init__()
		
		self.width = width
		self.height = height
	
	def __str__(self) -> str:
		width = int(self.width) if int(self.width) == self.width else self.width
		height = int(self.height) if int(self.height) == self.height else self.height
		return f"{{{width}, {height}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(width={self.width!r}, height={self.height!r})"


@archiving.struct_class
class CGVector(archiving.KnownStruct):
	struct_name = b"CGVector"
	field_encodings = [b"d", b"d"]
	
	dx: float
	dy: float
	
	def __init__(self, dx: float, dy: float) -> None:
		super().__init__()
		
		self.dx = dx
		self.dy = dy
	
	def __str__(self) -> str:
		dx = int(self.dx) if int(self.dx) == self.dx else self.dx
		dy = int(self.dy) if int(self.dy) == self.dy else self.dy
		return f"{{{dx}, {dy}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(dx={self.dx!r}, dy={self.dy!r})"


@archiving.struct_class
class CGRect(archiving.KnownStruct):
	struct_name = b"CGRect"
	field_encodings = [CGPoint.encoding, CGSize.encoding]
	
	origin: CGPoint
	size: CGSize
	
	def __init__(self, origin: CGPoint, size: CGSize) -> None:
		super().__init__()
		
		self.origin = origin
		self.size = size
	
	@classmethod
	def make(cls, x: float, y: float, width: float, height: float) -> "CGRect":
		return cls(CGPoint(x, y), CGSize(width, height))
	
	def __str__(self) -> str:
		return f"{{{self.origin}, {self.size}}}"
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(origin={self.origin!r}, size={self.size!r})"

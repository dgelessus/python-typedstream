from . import archiver


@archiver.struct_class
class NSPoint(archiver.KnownStruct):
	struct_name = b"_NSPoint"
	field_encodings = [b"f", b"f"]
	
	x: float
	y: float
	
	def __init__(self, x: float, y: float) -> None:
		super().__init__()
		
		self.x = x
		self.y = y
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(x={self.x!r}, y={self.y!r})"


@archiver.struct_class
class NSSize(archiver.KnownStruct):
	struct_name = b"_NSSize"
	field_encodings = [b"f", b"f"]
	
	width: float
	height: float
	
	def __init__(self, width: float, height: float) -> None:
		super().__init__()
		
		self.width = width
		self.height = height
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(width={self.width!r}, height={self.height!r})"


@archiver.struct_class
class NSRect(archiver.KnownStruct):
	struct_name = b"_NSRect"
	field_encodings = [NSPoint.encoding, NSSize.encoding]
	
	origin: NSPoint
	size: NSSize
	
	def __init__(self, origin: NSPoint, size: NSSize) -> None:
		super().__init__()
		
		self.origin = origin
		self.size = size
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}(origin={self.origin!r}, size={self.size!r})"

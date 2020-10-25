import typing

from .. import advanced_repr


class ArraySetBase(advanced_repr.AsMultilineStringBase):
	elements: typing.List[typing.Any]
	
	def _as_multiline_string_(self, *, state: advanced_repr.RecursiveReprState) -> typing.Iterable[str]:
		if not self.elements:
			count_desc = "empty"
		elif len(self.elements) == 1:
			count_desc = "1 element:"
		else:
			count_desc = f"{len(self.elements)} elements:"
		
		yield f"{type(self).__name__}, {count_desc}"
		
		for element in self.elements:
			for line in advanced_repr.as_multiline_string(element, calling_self=self, state=state):
				yield "\t" + line
	
	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.elements!r})"

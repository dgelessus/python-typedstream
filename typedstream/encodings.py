import typing


__all__ = [
	"split_encodings",
	"join_encodings",
	"parse_array_encoding",
	"build_array_encoding",
	"parse_struct_encoding",
	"build_struct_encoding",
	"anonymize_struct_names",
	"encoding_matches_expected",
	"all_encodings_match_expected",
]


# Adapted from https://github.com/beeware/rubicon-objc/blob/v0.3.1/rubicon/objc/types.py#L127-L188
# The type encoding syntax used in typedstreams is very similar,
# but not identical,
# to the one used by the Objective-C runtime.
# Some features are not used/supported in typedstreams,
# such as qualifiers, arbitrary pointers, object pointer class names, block pointers, etc.
# Typedstreams also use some type encoding characters that are not used by the Objective-C runtime,
# such as "+" for raw bytes and "%" for "atoms" (deduplicated/uniqued/interned C strings).
def _end_of_encoding(encoding: bytes, start: int) -> int:
	"""Find the end index of the encoding starting at index start.
	
	The encoding is not validated very extensively.
	There are no guarantees what happens for invalid encodings;
	an error may be raised,
	or a bogus end index may be returned.
	Callers are expected to check that the returned end index actually results in a valid encoding.
	"""
	
	if start not in range(len(encoding)):
		raise ValueError(f"Start index {start} not in range({len(encoding)})")
	
	paren_depth = 0
	
	i = start
	while i < len(encoding):
		c = encoding[i:i+1]
		if c in b"([{":
			# Opening parenthesis of some type, wait for a corresponding closing paren.
			# This doesn't check that the parenthesis *types* match
			# (only the *number* of closing parens has to match).
			paren_depth += 1
			i += 1
		elif paren_depth > 0:
			if c in b")]}":
				# Closing parentheses of some type.
				paren_depth -= 1
			i += 1
			if paren_depth == 0:
				# Final closing parenthesis, end of this encoding.
				return i
		else:
			# All other encodings consist of exactly one character.
			return i + 1
	
	if paren_depth > 0:
		raise ValueError(f"Incomplete encoding, missing {paren_depth} closing parentheses: {encoding!r}")
	else:
		raise ValueError(f"Incomplete encoding, reached end of string too early: {encoding!r}")


# Adapted from https://github.com/beeware/rubicon-objc/blob/v0.3.1/rubicon/objc/types.py#L430-L450
def split_encodings(encodings: bytes) -> typing.Iterable[bytes]:
	"""Split apart multiple type encodings contained in a single encoding string."""
	
	start = 0
	while start < len(encodings):
		end = _end_of_encoding(encodings, start)
		yield encodings[start:end]
		start = end


def join_encodings(encodings: typing.Iterable[bytes]) -> bytes:
	"""Combine a sequence of type encodings into a single type encoding string.
	
	.. note::
	
		This function currently doesn't perform any checking on its inputs
		and is currently equivalent to ``b"".join(encodings)``,
		but such checks may be added in the future.
		All elements of ``encodings`` should be valid type encoding strings.
	"""
	
	return b"".join(encodings)


def parse_array_encoding(array_encoding: bytes) -> typing.Tuple[int, bytes]:
	"""Parse an array type encoding into its length and element type encoding."""
	
	if not array_encoding.startswith(b"["):
		raise ValueError(f"Missing opening bracket in array type encoding: {array_encoding!r}")
	if not array_encoding.endswith(b"]"):
		raise ValueError(f"Missing closing bracket in array type encoding: {array_encoding!r}")
	
	i = 1
	while i < len(array_encoding) - 1:
		if array_encoding[i] not in b"0123456789":
			break
		i += 1
	length_string, element_type_encoding = array_encoding[1:i], array_encoding[i:-1]
	
	if not length_string:
		raise ValueError(f"Missing length in array type encoding: {array_encoding!r}")
	if not element_type_encoding:
		raise ValueError(f"Missing element type in array type encoding: {array_encoding!r}")
	
	return int(length_string.decode("ascii")), element_type_encoding


def build_array_encoding(length: int, element_type_encoding: bytes) -> bytes:
	"""Build an array type encoding from a length and an element type encoding.
	
	.. note::
	
		This function currently doesn't perform any checking on ``element_type_encoding``,
		but such checks may be added in the future.
		``element_type_encoding`` should always be a valid type encoding string.
	"""
	
	if length < 0:
		raise ValueError(f"Array length cannot be negative: {length}")
	
	length_string = str(length).encode("ascii")
	return b"[" + length_string + element_type_encoding + b"]"


def parse_struct_encoding(struct_encoding: bytes) -> typing.Tuple[bytes, typing.Sequence[bytes]]:
	"""Parse an array type encoding into its name and field type encodings."""
	
	if not struct_encoding.startswith(b"{"):
		raise ValueError(f"Missing opening brace in struct type encoding: {struct_encoding!r}")
	if not struct_encoding.endswith(b"}"):
		raise ValueError(f"Missing closing brace in struct type encoding: {struct_encoding!r}")
	
	try:
		equals_pos = struct_encoding.index(b"=")
	except ValueError:
		raise ValueError(f"Missing name in struct type encoding: {struct_encoding!r}")
	
	name = struct_encoding[1:equals_pos]
	field_type_encodings = list(split_encodings(struct_encoding[equals_pos+1:-1]))
	return name, field_type_encodings


def build_struct_encoding(name: bytes, field_type_encodings: typing.Iterable[bytes]) -> bytes:
	"""Build a struct type encoding from a name and field type encodings.
	
	.. note::
	
		This function currently doesn't perform any checking on ``field_type_encodings``,
		but such checks may be added in the future.
		All elements of ``field_type_encodings`` should be valid type encoding strings.
	"""
	
	return b"{" + name + b"=" + join_encodings(field_type_encodings) + b"}"


def anonymize_struct_names(encoding: bytes) -> bytes:
	"""Anonymize the names of all structs that appear in ``encoding``,
	i. e. replace their names with ``?``.
	
	Array and struct type encodings are parsed and their element/field types are anonymized recursively.
	If ``encoding`` doesn't contain named struct types anywhere,
	it is returned unchanged.
	
	This transformation is needed because struct names in typedstreams are sometimes replaced with ``?``,
	even if the struct has a name in the headers and is not actually anonymous.
	"""
	
	if encoding.startswith(b"{"):
		name, field_type_encodings = parse_struct_encoding(encoding)
		anonymized_field_type_encodings = [anonymize_struct_names(field_encoding) for field_encoding in field_type_encodings]
		return build_struct_encoding(b"?", anonymized_field_type_encodings)
	elif encoding.startswith(b"["):
		length, element_type_encoding = parse_array_encoding(encoding)
		anonymized_element_type_encoding = anonymize_struct_names(element_type_encoding)
		return build_array_encoding(length, anonymized_element_type_encoding)
	else:
		return encoding


def encoding_matches_expected(actual_encoding: bytes, expected_encoding: bytes) -> bool:
	"""Check whether ``actual_encoding`` matches ``expected_encoding``,
	accounting for struct names in ``actual_encoding`` possibly being anonymized.
	"""
	
	return (
		actual_encoding == expected_encoding
		or actual_encoding == anonymize_struct_names(expected_encoding)
	)


def all_encodings_match_expected(actual_encodings: typing.Sequence[bytes], expected_encodings: typing.Sequence[bytes]) -> bool:
	"""Check whether all of ``actual_encodings`` match ``expected_encodings``,
	accounting for struct names in ``actual_encodings`` possibly being anonymized.
	
	If ``actual_encodings`` and ``expected_encodings`` don't have the same length,
	they are considered to be not matching.
	"""
	
	return (
		len(actual_encodings) == len(expected_encodings)
		and all(
			encoding_matches_expected(actual, expected)
			for actual, expected in zip(actual_encodings, expected_encodings)
		)
	)

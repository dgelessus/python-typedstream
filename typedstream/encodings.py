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


__all__ = [
	"split_encodings",
	"join_encodings",
	"parse_array_encoding",
	"build_array_encoding",
	"parse_struct_encoding",
	"build_struct_encoding",
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


def parse_struct_encoding(struct_encoding: bytes) -> typing.Tuple[typing.Optional[bytes], typing.Sequence[bytes]]:
	"""Parse an array type encoding into its name and field type encodings."""
	
	if not struct_encoding.startswith(b"{"):
		raise ValueError(f"Missing opening brace in struct type encoding: {struct_encoding!r}")
	if not struct_encoding.endswith(b"}"):
		raise ValueError(f"Missing closing brace in struct type encoding: {struct_encoding!r}")
	
	try:
		# Stop searching for the equals if an opening brace
		# (i. e. the start of another structure type encoding)
		# is reached.
		# This is necessary to correctly handle struct types with no name that contain a struct type with a name,
		# such as b"{{foo=ii}}" (an unnamed struct containing a struct named "foo" containing two integers).
		try:
			end = struct_encoding.index(b"{", 1)
		except ValueError:
			end = -1
		equals_pos = struct_encoding.index(b"=", 1, end)
	except ValueError:
		name = None
		field_type_encoding_string = struct_encoding[1:-1]
	else:
		name = struct_encoding[1:equals_pos]
		field_type_encoding_string = struct_encoding[equals_pos+1:-1]
	
	field_type_encodings = list(split_encodings(field_type_encoding_string))
	return name, field_type_encodings


def build_struct_encoding(name: typing.Optional[bytes], field_type_encodings: typing.Iterable[bytes]) -> bytes:
	"""Build a struct type encoding from a name and field type encodings.
	
	.. note::
	
		This function currently doesn't perform any checking on ``field_type_encodings``,
		but such checks may be added in the future.
		All elements of ``field_type_encodings`` should be valid type encoding strings.
	"""
	
	field_type_encoding_string = join_encodings(field_type_encodings)
	if name is None:
		return b"{" + field_type_encoding_string + b"}"
	else:
		return b"{" + name + b"=" + field_type_encoding_string + b"}"


def encoding_matches_expected(actual_encoding: bytes, expected_encoding: bytes) -> bool:
	"""Check whether ``actual_encoding`` matches ``expected_encoding``,
	accounting for struct names in ``actual_encoding`` possibly being missing.
	"""
	
	if actual_encoding.startswith(b"{") and expected_encoding.startswith(b"{"):
		actual_name, actual_field_type_encodings = parse_struct_encoding(actual_encoding)
		expected_name, expected_field_type_encodings = parse_struct_encoding(expected_encoding)
		return (
			(actual_name in {None, b"?"} or actual_name == expected_name)
			and all_encodings_match_expected(actual_field_type_encodings, expected_field_type_encodings)
		)
	elif actual_encoding.startswith(b"[") and expected_encoding.startswith(b"["):
		actual_length, actual_element_type_encoding = parse_array_encoding(actual_encoding)
		expected_length, expected_element_type_encoding = parse_array_encoding(expected_encoding)
		return (
			actual_length == expected_length
			and encoding_matches_expected(actual_element_type_encoding, expected_element_type_encoding)
		)
	else:
		return actual_encoding == expected_encoding


def all_encodings_match_expected(actual_encodings: typing.Sequence[bytes], expected_encodings: typing.Sequence[bytes]) -> bool:
	"""Check whether all of ``actual_encodings`` match ``expected_encodings``,
	accounting for struct names in ``actual_encodings`` possibly being missing.
	
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

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


"""Implementation of an old binary property list format,
apparently originally from NeXTSTEP.
This format is *not* the same as the modern Mac OS X/macOS binary property list format,
which starts with the signature string ``bplist00`` and has a completely different structure.

This format supports only the following data types:

* ``nil`` (mapped to ``None``)
* ``NSData`` (mapped to ``bytes``)
* ``NSString`` (mapped to ``str``), stored in either of the following encodings:

  * UTF-16 with BOM. Both big-endian and little-endian byte order are allowed. Mac OS X/macOS always outputs this encoding.
  * The NeXTSTEP 8-bit character set. Mac OS X/macOS never outputs this encoding, but supports reading it.

* ``NSArray`` (mapped to ``list``), which can contain any supported data type as elements
* ``NSDictionary`` (mapped to ``dict``), which uses strings as keys and can contain any supported data type as values

We care about this format because it's used in Apple's implementation of -[NSArchiver encodePropertyList:] and -[NSUnarchiver decodePropertyList],
which are in turn used by some AppKit classes,
such as NSFont.

This format is also used by the Foundation classes NSSerializer and NSDeserializer.
These classes have been deprecated since Mac OS X 10.2,
and their header (<Foundation/NSSerialization.h>) was removed from the Mac OS X SDK some time between Mac OS X 10.4 and 10.7.
However, as of macOS 10.14,
these classes are still present and usable in the Foundation framework at runtime.

There is extremely little documentation on this format or the APIs that use it,
so this implementation is almost entirely based on examining the output of the relevant NSArchiver and NSSerializer methods.
Another deserializer implementation for this format can be found in the Darling project's Foundation implementation:
https://github.com/darlinghq/darling-foundation/blob/d3fe108d9d72e1ff4320129604bdb3de979ec82e/src/NSDeserializer.m
"""


import io
import typing


__all__ = [
	"deserialize_from_stream",
	"deserialize",
]


# Unicode mapping of the NeXTSTEP 8-bit character set.
# This mapping was created by taking a byte string containing all bytes from 0x01 through 0xfd (inclusive)
# and decoding it using the macOS Foundation framework as NSNEXTSTEPStringEncoding:
# This can be done from Python using rubicon-objc:
# objc.py_from_ns(NSString.alloc().initWithBytes(bytes(range(1, 254)), length=253, encoding=2))
# See also https://en.wikipedia.org/wiki/NeXT_character_set,
# although the mapping on the Wikipedia page doesn't exactly match the one used by macOS.
# The Wikipedia table indicates that character codes 0x60 and 0x27 correspond to opening and closing curly quotes (‘’),
# which is also documented in the NeXTSTEP 3.3 developer documentation linked from the Wikipedia page.
# However, macOS instead maps these codes to backtick/grave accent and straight quote (`'),
# which matches their meanings in plain 7-bit ASCII.
# For compatibility with macOS,
# we use the latter mapping.
_NEXTSTEP_8_BIT_CHARACTER_MAP = (
	'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f'
	'\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
	' !"#$%&\'()*+,-./'
	'0123456789:;<=>?'
	'@ABCDEFGHIJKLMNO'
	'PQRSTUVWXYZ[\\]^_'
	'`abcdefghijklmno'
	'pqrstuvwxyz{|}~\x7f'
	'\xa0ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏ'
	'ÐÑÒÓÔÕÖÙÚÛÜÝÞµ×÷'
	'©¡¢£⁄¥ƒ§¤’“«‹›ﬁﬂ'
	'®–†‡·¦¶•‚„”»…‰¬¿'
	'¹ˋ´ˆ˜¯˘˙¨²˚¸³˝˛ˇ'
	'—±¼½¾àáâãäåçèéêë'
	'ìÆíªîïðñŁØŒºòóôõ'
	'öæùúûıüýłøœßþÿ' # The last two bytes (0xfe and 0xff) are unassigned.
)


def _read_exact(stream: typing.BinaryIO, byte_count: int) -> bytes:
	"""Read ``byte_count`` bytes from ``stream`` and raise an exception if too few bytes are read
	(i. e. if EOF was hit prematurely).
	"""
	
	data = stream.read(byte_count)
	if len(data) != byte_count:
		raise ValueError(f"Attempted to read {byte_count} bytes of data, but only got {len(data)} bytes")
	return data


def deserialize_from_stream(stream: typing.BinaryIO) -> typing.Any:
	"""Deserialize an old binary plist from the given stream.
	
	This function stops and returns once the plist's root value has been fully read.
	It doesn't check that the stream has been fully consumed.
	Consider using :func:`deserialize` instead if you don't expect there to be any further data after the plist.
	"""
	
	type_number = int.from_bytes(_read_exact(stream, 4), "little")
	if type_number in {4, 5, 6}:
		# Byte-length-prefixed data/string
		data_length = int.from_bytes(_read_exact(stream, 4), "little")
		data = _read_exact(stream, data_length)
		align_padding = _read_exact(stream, (4 - data_length % 4) % 4)
		if align_padding != bytes(len(align_padding)):
			raise ValueError(f"Alignment padding after string/data should be all zero bytes, but got {align_padding!r}")
		
		if type_number == 4:
			# NSData
			return data
		elif type_number == 5:
			# NSString in NeXTSTEP 8-bit encoding
			return "".join(_NEXTSTEP_8_BIT_CHARACTER_MAP[byte] for byte in data)
		elif type_number == 6:
			# NSString in UTF-16 (with BOM) encoding
			return data.decode("utf-16")
		else:
			raise AssertionError(f"Unhandled type number: {type_number}")
	elif type_number in {2, 7}:
		element_count = int.from_bytes(_read_exact(stream, 4), "little")
		
		if type_number == 7:
			keys = []
			for _ in range(element_count):
				key = deserialize_from_stream(stream)
				if not isinstance(key, str):
					raise TypeError(f"Old plist dictionary key must be a string, not {type(key)}")
				keys.append(key)
		
		value_lengths = []
		for _ in range(element_count):
			value_lengths.append(int.from_bytes(_read_exact(stream, 4), "little"))
		
		values = []
		pos_before = stream.tell()
		for expected_length in value_lengths:
			value = deserialize_from_stream(stream)
			pos = stream.tell()
			if pos - pos_before != expected_length:
				raise ValueError(f"Expected value to be {expected_length} bytes long, but actual length is {pos - pos_before}")
			values.append(value)
			pos_before = pos
		
		if type_number == 2:
			# NSArray
			return values
		elif type_number == 7:
			# NSDictionary
			return dict(zip(keys, values))
		else:
			raise AssertionError(f"Unhandled type number: {type_number}")
	elif type_number == 8:
		# nil
		return None
	else:
		raise ValueError(f"Unknown/invalid type number: {type_number}")


def deserialize(data: bytes) -> typing.Any:
	"""Deserialize the given old binary plist data.
	
	This function checks that there is no remaining unused data after the end of the plist data.
	"""
	
	f = io.BytesIO(data)
	plist = deserialize_from_stream(f)
	remaining = len(data) - f.tell()
	if remaining != 0:
		raise ValueError(f"There are {remaining} bytes of data after the end of the plist")
	return plist

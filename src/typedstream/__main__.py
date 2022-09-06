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


import argparse
import sys
import typing


from . import __version__
from . import advanced_repr
from . import archiving
from . import stream


def make_subcommand_parser(subs: typing.Any, name: str, *, help: str, description: str, **kwargs: typing.Any) -> argparse.ArgumentParser:
	"""Add a subcommand parser with some slightly modified defaults to a subcommand set.
	
	This function is used to ensure that all subcommands use the same base configuration for their ArgumentParser.
	"""
	
	ap = subs.add_parser(
		name,
		formatter_class=argparse.RawDescriptionHelpFormatter,
		help=help,
		description=description,
		allow_abbrev=False,
		add_help=False,
		**kwargs,
	)
	
	ap.add_argument("--help", action="help", help="Display this help message and exit.")
	
	return ap


def open_typedstream_file(file: str) -> stream.TypedStreamReader:
	if file == "-":
		return stream.TypedStreamReader(sys.stdin.buffer)
	else:
		return stream.TypedStreamReader.open(file)


def dump_typedstream(ts: stream.TypedStreamReader) -> typing.Iterable[str]:
	yield f"streamer version {ts.streamer_version}, byte order {ts.byte_order}, system version {ts.system_version}"
	yield ""
	indent = 0
	next_object_number = 0
	for event in ts:
		if isinstance(event, (stream.EndTypedValues, stream.EndObject, stream.EndArray, stream.EndStruct)):
			indent -= 1
		
		rep = ("\t" * indent) + str(event)
		if isinstance(event, (stream.CString, stream.SingleClass, stream.BeginObject)):
			rep += f" (#{next_object_number})"
			next_object_number += 1
		yield rep
		
		if isinstance(event, (stream.BeginTypedValues, stream.BeginObject, stream.BeginArray, stream.BeginStruct)):
			indent += 1


def do_read(ns: argparse.Namespace) -> typing.NoReturn:
	with open_typedstream_file(ns.file) as ts:
		for line in dump_typedstream(ts):
			print(line)
	
	sys.exit(0)


def dump_decoded_typedstream(ts: stream.TypedStreamReader) -> typing.Iterable[str]:
	unarchiver = archiving.Unarchiver(ts)
	for obj in unarchiver.decode_all():
		yield from advanced_repr.as_multiline_string(obj)


def do_decode(ns: argparse.Namespace) -> typing.NoReturn:
	with open_typedstream_file(ns.file) as ts:
		for line in dump_decoded_typedstream(ts):
			print(line)
	
	sys.exit(0)


def main() -> typing.NoReturn:
	"""Main function of the CLI.
	
	This function is a valid setuptools entry point.
	Arguments are passed in sys.argv,
	and every execution path ends with a sys.exit call.
	(setuptools entry points are also permitted to return an integer,
	which will be treated as an exit code.
	We do not use this feature and instead always call sys.exit ourselves.)
	"""
	
	ap = argparse.ArgumentParser(
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description="""
%(prog)s is a tool for dumping typedstream files, which are produced by
the NSArchiver class in Apple's Foundation framework, as well as the
NXTypedStream APIs in the older NeXTSTEP OS.
""",
		allow_abbrev=False,
		add_help=False,
	)
	
	ap.add_argument("--help", action="help", help="Display this help message and exit.")
	ap.add_argument("--version", action="version", version=__version__, help="Display version information and exit.")
	
	subs = ap.add_subparsers(
		dest="subcommand",
		metavar="SUBCOMMAND",
	)
	
	sub_read = make_subcommand_parser(
		subs,
		"read",
		help="Read and display the raw contents of a typedstream.",
		description="""
Read and display the raw contents of a typedstream.

All information is displayed as it's stored in the typedstream and is processed
as little as possible. In particular, object references are not resolved
(although each object's reference number is displayed, so that the references
can be followed manually), and objects aren't handled differently based on
their class.
""",
	)
	sub_read.add_argument("file", help="The typedstream file to read, or - for stdin.")
	
	sub_decode = make_subcommand_parser(
		subs,
		"decode",
		help="Read, decode and display the contents of a typedstream.",
		description="""
Read, decode and display the contents of a typedstream.

Where possible, the data read from the typedstream is decoded into a
higher-level structure before being displayed. Objects are decoded based on
their class when their format is known and implemented. Objects of unknown
classes are also supported, but are decoded to a generic format based on the
typedstream data.

As a result of this decoding, some low-level information from the typedstream
is discarded and not displayed, such as raw type encoding strings in known
classes, and object reference numbers. To see this low-level information,
use the read subcommand instead.
""",
	)
	sub_decode.add_argument("file", help="The typedstream file to read, or - for stdin.")
	
	ns = ap.parse_args()
	
	if ns.subcommand is None:
		print("Missing subcommand", file=sys.stderr)
		sys.exit(2)
	elif ns.subcommand == "read":
		do_read(ns)
	elif ns.subcommand == "decode":
		do_decode(ns)
	else:
		print(f"Unknown subcommand: {ns.subcommand!r}", file=sys.stderr)
		sys.exit(2)


if __name__ == "__main__":
	sys.exit(main())

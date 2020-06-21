import argparse
import sys
import typing


from . import __version__, api


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
		help="Read and display the contents of a typedstream file.",
		description="""
Read and display the contents of a typedstream file.
""",
	)
	sub_read.add_argument("file", type=argparse.FileType("rb"), help="The typedstream file to read.")
	
	ns = ap.parse_args()
	
	if ns.subcommand is None:
		print("Missing subcommand", file=sys.stderr)
		sys.exit(2)
	elif ns.subcommand == "read":
		with ns.file, api.TypedStreamReader(ns.file) as ts:
			while True:
				try:
					values = ts.read_values(end_of_stream_ok=True)
				except EOFError:
					break
				
				for value in values:
					print(value)
		sys.exit(0)
	else:
		print(f"Unknown subcommand: {ns.subcommand!r}", file=sys.stderr)
		sys.exit(2)


if __name__ == "__main__":
	sys.exit(main())

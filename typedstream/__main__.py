import sys
import typing


def main() -> typing.NoReturn:
	"""Main function of the CLI.
	
	This function is a valid setuptools entry point.
	Arguments are passed in sys.argv,
	and every execution path ends with a sys.exit call.
	(setuptools entry points are also permitted to return an integer,
	which will be treated as an exit code.
	We do not use this feature and instead always call sys.exit ourselves.)
	"""
	
	raise NotImplementedError("CLI not implemented yet") # TODO


if __name__ == "__main__":
	sys.exit(main())

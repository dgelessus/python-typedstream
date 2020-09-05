``typedstream``
===============

A pure Python, cross-platform library/tool for reading Mac OS X and NeXTSTEP typedstream files.

The typedstream format is a serialization format for C and Objective-C data structures.
It is used by Apple's implementation of the Foundation classes `NSArchiver <https://developer.apple.com/documentation/foundation/nsarchiver?language=objc>`__ and `NSUnarchiver <https://developer.apple.com/documentation/foundation/nsunarchiver?language=objc>`__,
and is based on the data format originally used by NeXTSTEP's ``NXTypedStream`` APIs.

The NSArchiver and NSUnarchiver classes and the typedstream format are superseded by `NSKeyedArchiver <https://developer.apple.com/documentation/foundation/nskeyedarchiver?language=objc>`__ and `NSKeyedUnarchiver <https://developer.apple.com/documentation/foundation/nskeyedunarchiver?language=objc>`__,
which use binary property lists for serialization.
NSArchiver and NSUnarchiver are deprecated since macOS 10.13 (but still available as of macOS 10.15)
and have never been available for application developers on other Apple platforms (iOS, watchOS, tvOS).
Despite this,
the typedstream data format is still used by some macOS components and applications,
such as the Stickies and Grapher applications.

.. note::

    The typedstream data format is undocumented and specific to the Mac OS X implementation of NSArchiver/NSUnarchiver.
    Other Objective-C/Foundation implementations may also provide NSArchiver/NSUnarchiver,
    but might not use the same data format.
    For example,
    GNUstep's NSArchiver/NSUnarchiver implementations use a completely different format,
    with a `GNUstep archive` signature string.

Features
--------

* Pure Python, cross-platform - no native Mac APIs are used.
* Provides both a Python API (for use in programs and in the REPL)
  and a command-line tool (for quick inspection of files from the command line).
* Typedstream data is automatically parsed and translated to appropriate Python data types.

  * Unlike with the Objective-C `NSCoder <https://developer.apple.com/documentation/foundation/nscoder?language=objc>`__ API,
    there is no need to explicitly provide the types of all values in order to read them.

Requirements
------------

Python 3.6 or later.
No other libraries are required.

Installation
------------

``typedstream`` is compatible with Python 3.6 or later.

``typedstream`` is unfinished and unreleased,
so it is not available on PyPI yet.
If you want to use it anyway,
you need to clone/download the source code and install it by running this ``pip`` command in the source directory:

.. code-block:: sh

    python3 -m pip install .

If you update your clone or otherwise modify the code,
you need to re-run the install command.
You can get around the reinstall requirement by installing the package in "editable" mode:

.. code-block:: sh

    python3 -m pip install --editable .

In editable mode,
changes to the source code take effect immediately without a reinstall.
This doesn't work perfectly in all cases though,
especially if the package metadata
(pyproject.toml, setup.cfg, setup.py, ``__version__``, etc.)
has changed.
If you're using an editable install and experience any problems with the package,
please try re-running the editable install command,
and if that doesn't help,
try using a regular (non-editable) installation instead.

Examples
--------

TODO

Command-line interface
^^^^^^^^^^^^^^^^^^^^^^

TODO

Limitations
-----------

This library only understands the basic structure of typedstream data.
It decodes the typedstream format's low-level type information and data format
into matching Python data types and recreates the references between objects.
However,
it does not have any knowledge about the high-level meaning of the values and objects,
so it cannot automatically convert these values and objects into meaningful high-level data structures.

How each class encodes its data in a typedstream is almost never documented,
and the relevant Objective-C implementation source code is often not available,
so usually the only way to find out the meaning of the values in a typedstream is through experimentation and educated guessing.

Writing typedstream data is not supported at all.

Changelog
---------

Version 0.0.1 (next version)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Initial development version.

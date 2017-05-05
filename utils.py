# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function
import os.path
import sys
from collections import namedtuple

def getDirectoryPath(directory):
	# This is needed for py2exe
	try:
		if sys.frozen or sys.importers:
			return os.path.join(os.path.dirname(sys.executable), directory)
	except AttributeError:
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", directory)

def has_generator_started(g):
	return not (g.gi_frame is not None and g.gi_frame.f_lasti == -1)
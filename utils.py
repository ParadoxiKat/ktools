# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function
import argparse
import datetime
import imp
import os, os.path
import sys
import time

def main_is_frozen():
	return (hasattr(sys, "frozen") or # new py2exe
		hasattr(sys, "importers") # old py2exe
		or imp.is_frozen("__main__")) # tools/freeze

def getDirectoryPath(directory):
	# This is needed for py2exe
	try:
		if sys.frozen or sys.importers:
			return os.path.join(os.path.dirname(sys.executable), directory)
	except AttributeError:
		return os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", directory)

def has_generator_started(g):
	return not (g.gi_frame is not None and g.gi_frame.f_lasti == -1)

def valid_date_type(arg_date_str):
	"""custom argparse *date* type for user dates values given from the command line"""
	dashes = arg_date_str.count('-')
	date_str = arg_date_str
	if dashes == 1:
		date_str = '{}{}{}'.format(time.localtime().tm_year, '-', arg_date_str)
	elif dashes == 2:
		date_lst = arg_date_str.split('-')
		if len(date_lst[2]) == 4:
			date_str = '{}-{}-{}'.format(date_lst[2], date_lst[0], date_lst[1])
	try:
		return datetime.date(*time.strptime(date_str, "%Y-%m-%d")[:3])
	except ValueError:
		msg = "Given Date ({0}) not valid! Expected format, YYYY-MM-DD!".format(arg_date_str)
		raise argparse.ArgumentTypeError(msg)

def date_to_timestamp(date):
	"""Return the timestamp of the supplied datetime.date instance as number of seconds since the epoch."""
	return time.mktime(date.timetuple())

def prev_date(date):
	"""Return a datetime.date instance for the date prior to the supplied date."""
	return datetime.date.fromtimestamp(date_to_timestamp(date)-86400)

def next_date(date):
	"""Return a datetime.date instance for the date after the supplied date."""
	return datetime.date.fromtimestamp(date_to_timestamp(date)+86400)

def yesterday():
	"""Return yesterday's datetime.date instance."""
	return prev_date(datetime.date.today())
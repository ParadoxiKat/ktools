# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import datetime
import logging
logger=logging.getLogger(__name__)
import time
from .config import Config, config_lock
from .utils import valid_date_type

debug_level = None

def init_debugging(prog_name='', parser=None, desc='uninteresting', filename='debug.log', filemode='w', format='%(levelname)s: from %(name)s in %(threadName)s: "%(message)s" @ %(asctime)s.%(msecs)d', datefmt='%m/%d/%Y %H:%M:%S'):
	"""initializes debugging system.
	
	Checks for debugging values in config file, and on command line.
	Sets the appropriate level, and if necessary initializes logging.
	
	keyword arguments:
	parser -- argparse.ArgumentParser instance to use. If set to None, one is created. (default None)
	desc -- description string to use *only* if parser == None. If a parser is supplied this argument is ignored. (default 'uninteresting')
	filename -- name of the log file. (default debug.log)
	filemode -- mode to open file. (default w)
	format -- format of log messages. (default '%(levelname)s: from %(name)s in %(threadName)s: "%(message)s" @ %(asctime)s.%(msecs)d')
	datefmt -- format of the date part of log messages. (default '%m/%d/%Y %H:%M:%S')
	
	returns: the parser that was supplied, or created if not supplied.
	"""
	global debug_level
	with config_lock:
		c=Config(prog_name=prog_name)
		try:
			debug_level = c['debug_level']
			if debug_level not in logging._levelNames:
				if isinstance(debug_level, int):
					if debug_level * 10 in logging._levelNames:
						debug_level *= 10
					elif debug_level - debug_level % 10 in logging._levelNames:
						debug_level -= debug_level % 10
					else:
						debug_level = None
				else:
					debug_level = debug_level.upper()
			if not isinstance(debug_level, int):
				debug_level = logging._levelNames[debug_level]
		except (KeyError, AttributeError):
			debug_level = None
		finally:
			if 'debug_level' not in c or debug_level != c['debug_level']:
				c['debug_level'] = debug_level
				c.save()
		del c
	if parser is None: parser = argparse.ArgumentParser(description=desc)
	parser.add_argument("-D", "--debug", help="Debug level. 0-5 or one of none|debug|info|warning|error|critical.", choices=('0', 'none', '1', 'debug', '2', 'info', '3', 'warning', '4', 'debug', '5', 'critical'))
	args=parser.parse_args()
	if args.debug:
		try:
			debug_level = int(args.debug)*10
		except ValueError:
			if args.debug.lower() == 'none': debug_level = None
			else: debug_level = logging._levelNames[args.debug.upper()]
	if debug_level is not None and debug_level != 0:
		logging.basicConfig(filename=filename, filemode=filemode, level=debug_level, format=format, datefmt=datefmt)
		logger.debug('debugging initialized')
	return parser, args

def dateargs(parser=None, desc='uninteresting', default=None, help='date string'):
	"""adds date-handling arguments.
	
	Adds -d, --date argument that accepts various date strings and stores as datetime.date instances to the supplied parser.
	If no parser is supplied, one is created.
	
	keyword arguments:
	parser -- argparse.ArgumentParser instance to use. If None, one is created. (default None)
	desc -- description to use for parser if one is created. (default 'uninteresting')
	default -- default date if argument isn't supplied. If None, defaults to datetime.date.today(). (default None)
	help -- message to use for help string of date option. Format instructions are appended. (default 'date string')
	
	returns: The supplied or created parser.
	"""
	if parser is None: parser = argparse.ArgumentParser(description=desc)
	parser.add_argument('-d', '--date', dest='date', type=valid_date_type, default=default or datetime.date.today(), help='{}\n    Valid formats are "YYYY-MM-DD", "MM-DD-YYYY", "MM-DD" which defaults to this year or "DD"for number of days ago.'.format(help))
	return parser


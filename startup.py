import argparse
import datetime
import logging
import time
from .config import Config, config_lock
from .utils import valid_date_type, yesterday


with config_lock:
	c=Config()
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

parser = argparse.ArgumentParser(description="")
parser.add_argument("-D", "--debug", help="Debug level. 0-5 or one of none|debug|info|warning|error|critical.", choices=('0', 'none', '1', 'debug', '2', 'info', '3', 'warning', '4', 'debug', '5', 'critical'))
args=parser.parse_args()

if args.debug:
	try:
		debug_level = int(args.debug)*10
	except ValueError:
		if args.debug.lower() == 'none': debug_level = None
		else: debug_level = logging._levelNames[args.debug.upper()]

if debug_level is not None and debug_level != 0:
	logging.basicConfig(filename='debug.log', filemode='w', level=debug_level, format='%(levelname)s: from %(name)s in %(threadName)s: "%(message)s" @ %(asctime)s.%(msecs)d', datefmt='%m/%d/%Y %H:%M:%S')

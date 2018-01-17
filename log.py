# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import os
import time
import zipfile

LOG_FMT_STR = '%(levelname)s: "%(message)s" from %(name)s in %(threadName)s @ %(asctime)s.%(msecs)d'
LOG_DATEFMT_STR = '%m-%d-%Y %H:%M:%S'

def initlog(**kwargs):
	filename = (kwargs.get('filename') or kwargs.get('logfile', 'debug.log'))
	mode = (kwargs.get('mode') or kwargs.get('logfilemode', 'w'))
	level = (kwargs.get('level') or kwargs.get('loglevel', 0))
	if isinstance(level, int): level = _fix_level_number(level)
	format = (kwargs.get('format') or kwargs.get('logfileformat', LOG_FMT_STR))
	datefmt = (kwargs.get('datefmt') or kwargs.get('logfiledatefmt', LOG_DATEFMT_STR))
	stream = kwargs.get('stream')
	stream_level = kwargs.get('stream_level', level)
	if isinstance(stream_level, int): stream_level = _fix_level_number(stream_level)
	stream_format = kwargs.get('stream_format', format)
	stream_datefmt = kwargs.get('stream_datefmt', datefmt)
	keeplogs = kwargs.get('keeplogs', 5)
	zip = kwargs.get('ziplogs', True)
	if not os.path.isabs(filename): filename = os.path.abspath(filename)
	if keeplogs and os.path.exists(filename) and os.path.getsize(filename): rotatelog(filename, count=keeplogs, zip=zip)
	fh = logging.FileHandler(filename, mode=mode)
	if stream is not None: sh = logging.StreamHandler(stream)
	else: sh = None
	fmt = logging.Formatter(format, datefmt)
	fh.setFormatter(fmt)
	if sh is not None:
		if stream_format is stream_datefmt is None: fmt2 = fmt
		else: fmt2 = logging.Formatter(stream_format, stream_datefmt)
		sh.setFormatter(fmt2)
	logging.root.addHandler(fh)
	logging.root.setLevel(level)
	if sh is not None:
		logging.root.addHandler(sh)
		if stream_level is not None: sh.setLevel(stream_level)
	return filename

def _fix_level_number(level):
	if level < 0 or level > 5: raise ValueError('Log level must be between 0 and 5.')
	return (((level-3)*-1)+3)*10

def get_logging_parser(parents=[]):
	parser = argparse.ArgumentParser(add_help=False, parents=parents)
	group = parser.add_argument_group(title='Logging options', description='Set how much logging you want, and where you want it to go.')
	xgroup = group.add_mutually_exclusive_group(required=False)
	xgroup.add_argument('--stdout', type=lambda x:x if x==-1 else valid_log_level(x), nargs='?', const=-1, help='Log to standard output (stdout). If no level is supplied, use the same level as log to file. Note that this option cannot be used with the --stderr option.')
	xgroup.add_argument('--stderr', type=lambda x:x if x==-1 else valid_log_level(x), nargs='?', const=-1, help='Log to standard error (stderr). If no level is supplied, use the same level as log to file. Note that this option cannot be used with the --stdout option.')
	group.add_argument('-L', '--log-level', dest='loglevel', type=valid_log_level, help='Level of log output. Levels are:\n\t0 - No logging (the default) | 5 - most logging.\n\tYou may also use the logging level names "none | critical | error | warning | info | debug"')
	group.add_argument('--log-file', dest='logfile', help='Path to log file.')
	group.add_argument('--keeplogs', dest='keeplogs', type=int, default=5, help='Number of old log files to keep. Default is 5.')
	return parser

def rotatelog(filepath, count=5, zip=True):
	if not os.path.isabs(filepath): filepath = os.path.abspath(filepath)
	dirname = os.path.dirname(filepath)
	basename = os.path.basename(filepath)
	files = os.listdir(dirname)
	for f in files[:]:
		if f == basename or not f.startswith(basename): files.remove(f)
	files.sort()
	if len(files) >= count:
		files, remove = files[:count-1], files[count-1:]
		for f in remove: os.remove(f)
	newfilepath = '{}-{}'.format(filepath, time.strftime('%Y%m%d-%H%M%S', time.localtime(os.path.getctime(filepath))))
	os.rename(filepath, newfilepath)
	if zip:
		ziplog(newfilepath)
		os.remove(newfilepath)

def valid_log_level(level):
	if level.isdigit():
		level = int(level)
		if level >= 0 and level <=5: return level
		raise ValueError('Valid levels are between 0 and 5')
	else:
		levels =('NONE', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG')
		level = level.upper()
		if level in levels: return level
		raise ValueError('{} is not a valid level name.\n\tValid names are {}'.format(level, levels))

def ziplog(filename):
	zname = '{}.zip'.format(filename)
	z = zipfile.ZipFile(zname, 'w', zipfile.ZIP_DEFLATED)
	z.write(filename, arcname=os.path.basename(filename))
	z.close()
	return zname

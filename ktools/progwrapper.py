# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function
import argparse
from collections import defaultdict
import datetime
import logging
logger=logging.getLogger(__name__)
import os
import sys
import time
import traceback
from .config import Config, get_config_parser
from .log import *
from .utils import get_exe_path, get_program_path, get_settings_path, is_exc_info, valid_date_type, sendmail

class _Handler(object):
	def __init__(self, func, args=None, kwargs=None):
		self.func = func
		self.args = args or []
		self.kwargs = kwargs or {}
		logger.debug("Created _Handler {}, using function {} with args {} and kwargs {}".format(self, self.func, self.args, self.kwargs))

	def __call__(self):
		self.func(*self.args, **self.kwargs)

class ProgWrapper(object):
	def __init__(self, **opts):
		self._startup_handlers = defaultdict(set)
		self._cleanup_handlers = defaultdict(set)
		if 'progname' not in opts:
			opts['progname'] = os.path.basename(sys.argv[0]) or os.path.basename(sys.executable)
			logger.debug('"progname" not supplied, defaulting to "{}"'.format(opts['progname']))
		if 'datadir' not in opts: opts['datadir'] = ''
		logger.debug('datadir: {}'.format(opts['datadir']))
		opts['program_path'] = get_program_path(opts['datadir'])
		logger.debug('program_path: {}'.format(opts['program_path']))
		opts['exe_path'] = get_exe_path(opts['datadir'])
		logger.debug('exe_path: {}'.format(opts['exe_path']))
		opts['settings_path'] = get_settings_path(opts['progname'], opts['datadir'])
		if not os.path.exists(opts['settings_path']): os.makedirs(opts['settings_path'])
		logger.debug('settings_path: {}'.format(opts['settings_path']))
		parser = opts.get('parser')
		if parser is not None:
			parent_parsers = [parser]
			del opts['parser']
		else: parent_parsers = []
		opts['parent_parsers'] = parent_parsers
		self.opts = opts
		self.add_startup_handler(self.args_startup, priority=0)
		self.add_startup_handler(self.config_startup, priority=1)
		self.add_startup_handler(self.logging_startup, priority=2)
		self.add_cleanup_handler(self.config_cleanup, priority=97)
		self.add_cleanup_handler(self.logging_cleanup, priority=98)
		self.add_cleanup_handler(self.send_report, priority=99)

	def __enter__(self):
		for priority in sorted(self._startup_handlers.keys()):
			handlers = self._startup_handlers[priority]
			for handler in handlers: handler()
		return self

	def __exit__(self, exc_type, exc_val, tb):
		self.opts['exc_info'] = exc_info = (exc_type, exc_val, tb)
		if exc_type is SyntaxError: raise
		if exc_type not in (None, SystemExit, KeyboardInterrupt):
			logging.exception('Unhandled exception.')
			self.make_crash_report(self.opts)
		for priority in sorted(self._cleanup_handlers.keys()):
			handlers = self._cleanup_handlers[priority]
			for handler in handlers: handler()

	def add_startup_handler(self, func, priority=5, args=[], kwargs={}):
		if self.opts not in args: args.append(self.opts)
		self._startup_handlers[priority].add(_Handler(func, args=args, kwargs=kwargs))

	def add_cleanup_handler(self, func, priority=5, args=[], kwargs={}):
		if self.opts not in args: args.append(self.opts)
		self._cleanup_handlers[priority].add(_Handler(func, args=args, kwargs=kwargs))

	def args_startup(self, opts):
		parent_parsers = opts.get('parent_parsers', [])
		if opts.get('config_args', False): parent_parsers.append(get_config_parser())
		if opts.get('logging_args', False): parent_parsers.append(get_logging_parser())
		opts['parent_parsers'] = parent_parsers
		opts['parser'] = argparse.ArgumentParser(parents=parent_parsers)

	def config_startup(self, opts):
		exepath = opts['exe_path']
		progpath = opts['program_path']
		settingspath = opts['settings_path']
		#if not os.path.exists(settingspath): os.makedirs(settingspath)
		c = Config(progpath, exepath, settingspath, arg_configs=opts.get('arg_configs', False), envvars_as_keys=opts.get('envvars_as_keys', False), parser=opts['parser'], add_logging_args=True)
		opts['config'] = c

	def config_cleanup(self, opts):
		save = opts.get('save_config_on_exit', False)
		if save: opts['config'].save()

	def logging_startup(self, opts):
		c = opts['config']
		if not c.get('loglevel'): return
		if c['stdout']: stream = sys.stdout
		elif c['stderr']: stream = sys.stderr
		else: stream = None
		if stream: stream_level = c['stdout'] or c['stderr']
		else: stream_level = None
		logfile = initlog(stream=stream, stream_level=stream_level, **c)
		opts['logfile'] = logfile
		logging.info('Initialized')

	def logging_cleanup(self, opts):
		if not logging.root.handlers: return
		logging.info('Shutting down.')
		logging.shutdown()

	def make_crash_report(self, opts):
		tb = opts['traceback'] = ''.join(traceback.format_exception(*opts['exc_info']))
		if opts.get('print_tb'): print(tb)
		subject = '{} crashed at {}'.format(opts['progname'], time.asctime())
		message = 'OOPSE!\n\n{} just crashed. Here\'s the traceback:\n{}\n'.format(opts['progname'], tb)
		attachments = set([opts.get('logfile', '')]) if opts.get('logfile') else set()
		report = opts.get('report', {})
		report['subject'] = ' + '.join((report.get('subject', ''), subject)) if report.get('subject') else subject
		report['message'] = '{}\n\n{}\n\n{}'.format(message, '-'*20, report.get('message', '')) if report.get('message') else message
		report['attachments'] = report.get('attachments', set()) | attachments
		opts['report'] = report

	def send_report(self, opts):
		handler = opts.get('send_report')
		report = opts.get('report')
		cfg = opts['config']
		sender, recipient, smtphost = cfg.get('crash_sender'), cfg.get('crash_recipient'), cfg.get('crash_host')
		if not handler and all((sender, recipient, smtphost)): handler = lambda r:sendmail(sender, recipient, r['message'], smtphost=smtphost, subject=r['subject'], attach=r.get('attachments'))
		if handler and report: handler(report)

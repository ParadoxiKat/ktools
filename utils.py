# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import print_function
import argparse
import datetime
from email import encoders
from email.message import Message
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imp
from importlib import import_module
import inspect
import mimetypes
import os, os.path
import smtplib
import sys
import time
import traceback
from warnings import warn

COMMASPACE = ', '


def is_frozen():
	frozen = getattr(sys, "frozen", False) # new py2exe, py2app
	if frozen is True: frozen = 'cx_freeze'
	if not frozen:
		if getattr(sys, "importers", False): frozen = 'old_py2exe'# old py2exe
		elif imp.is_frozen("__main__"): frozen = 'tools/freeze'# tools/freeze
	return frozen

def get_program_path(*subdirs):
	frozen = is_frozen()
	mainpath = getattr(sys.modules['__main__'], '__file__', None)
	if frozen: path = os.path.dirname(os.path.realpath(sys.executable))
	elif mainpath: path = os.path.dirname(os.path.realpath(mainpath))
	else: path = os.path.realpath(os.getcwd())
	return os.path.join(path, *subdirs)

def get_settings_path(name, *subdirs):
	userpath = os.path.join(get_program_path(), 'userconfig')
	if os.path.exists(userpath) and os.path.isdir(userpath): path = userpath
	elif sys.platform in ('cygwin', 'win32'):
		if 'APPDATA' in os.environ:
			path = os.path.join(os.environ['APPDATA'], name)
		else:
			path = os.path.expanduser('~/%s' % name)
	elif sys.platform == 'darwin':
		path = os.path.expanduser('~/Library/Application Support/%s' % name)
	elif sys.platform.startswith('linux') or "bsd"in sys.platform:
		if 'XDG_CONFIG_HOME' in os.environ:
			path = os.path.join(os.environ['XDG_CONFIG_HOME'], name)
		else:
			path = os.path.expanduser('~/.config/%s' % name)
	else:
		path = os.path.expanduser('~/.%s' % name)
	return os.path.join(path, *subdirs)

def whoami(n=0):
	"""return the name of the function that calls this function. Optional argument n for number of frames to go back"""
	return sys._getframe(n+1).f_code.co_name

def load_modules(n=1):
	module = inspect.getmodule(sys._getframe(n)) # the module that called this function
	filenames = set()
	for filename in os.listdir(module.__path__[0]):	
		if filename.startswith('_'): continue
		filenames.add(filename.rsplit('.', 1)[0])
	modules = set()
	for filename in filenames:
		try:
			modules.add(import_module('.{}'.format(filename), module.__package__))
		except Exception as e:
			print('Failed loading module {}.\n{}'.format(filename, traceback.format_exc()))
	return modules

def has_generator_started(g):
	"""return True if generator g has started running, False otherwise."""
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
		if dashes == 0:
			return datetime.date.fromtimestamp(time.time()-(86400*int(arg_date_str)))
		else:
			return datetime.date(*time.strptime(date_str, "%Y-%m-%d")[:3])
	except ValueError:
		msg = "Given Date ({0}) not valid! Expected formats: YYYY-MM-DD, MM-DD-YYYY, MM-DD- or DD for number of days ago.".format(arg_date_str)
		raise argparse.ArgumentTypeError(msg)

def date_to_timestamp(date):
	"""Return the timestamp of the supplied datetime.date instance as number of seconds since the epoch."""
	return time.mktime(date.timetuple())

def prev_date(date, days=1):
	"""Return a datetime.date instance for the date prior to the supplied date."""
	return datetime.date.fromtimestamp(date_to_timestamp(date)-(86400*days))

def next_date(date, days=1):
	"""Return a datetime.date instance for the date after the supplied date."""
	return datetime.date.fromtimestamp(date_to_timestamp(date)+(86400*days))

def yesterday():
	"""Return yesterday's datetime.date instance."""
	return prev_date(datetime.date.today())

def tryimport(modules, obj=None, message=None):
			#Original version of this function copied from the circuits.tools module.
		#See circuits at http://circuitsframework.com/
	modules = (modules,) if isinstance(modules, str) else modules
	for module in modules:
		try:
			m = __import__(module, globals(), locals())
			return getattr(m, obj) if obj is not None else m
		except:
			pass
	if message is not None:
		warn(message)

def _get_mime_msg(path, recursive=False):
	"""Get MIME messages from a file or directory.
	
	Return a MIME Message for path, if path is a file.
	if path is a directory, return Messages for each file.
	if recursive is True, recurse into subdirectories.
	
	Parameters:
	path -- the path to get a Message or Messages for.
	
	Keyword Arguments:
	recursive -- whether or not to recurse into subdirectories (default False)
	
	returns -- list of MIME Messages
	"""
	if not os.path.exists(path): raise ValueError('Path does not exist: {}'.format(path))
	messages = []
	if os.path.isdir(path):
		for filename in os.listdir(path):
			_path = os.path.sep.join((path, filename))
			if (recursive and os.path.isdir(_path)) or os.path.isfile(_path): messages += _get_mime_msg(_path)
	elif os.path.isfile(path):
		# Guess the content type based on the file's extension.  Encoding
		# will be ignored, although we should check for simple things like
		# gzip'd or compressed files.
		print(path)
		ctype, encoding = mimetypes.guess_type(path)
		if ctype is None or encoding is not None:
			# No guess could be made, or the file is encoded (compressed), so
			# use a generic bag-of-bits type.
			ctype = 'application/octet-stream'
		maintype, subtype = ctype.split('/', 1)
		if maintype == 'text':
			fp = open(path)
			# Note: we should handle calculating the charset
			msg = MIMEText(fp.read(), _subtype=subtype)
			fp.close()
		elif maintype == 'image':
			fp = open(path, 'rb')
			msg = MIMEImage(fp.read(), _subtype=subtype)
			fp.close()
		elif maintype == 'audio':
			fp = open(path, 'rb')
			msg = MIMEAudio(fp.read(), _subtype=subtype)
			fp.close()
		else:
			fp = open(path, 'rb')
			msg = MIMEBase(maintype, subtype)
			msg.set_payload(fp.read())
			fp.close()
			# Encode the payload using Base64
			encoders.encode_base64(msg)
		# Set the filename parameter
		msg.add_header('Content-Disposition', 'attachment', filename=path.rsplit(os.path.sep, 1)[-1])
		messages = [msg]
	return messages

def sendmail(sender, recipient, text, smtphost='localhost', subject='', attach=None, recursive=False):
	"""Send email.
	
	Send an email. Optionally attach files.
	
	Parameters:
	sender -- sending email address.
	recipient -- single email address as str or list of email addresses to send to.
	text -- texxt of the email.
	
	Keyword Arguments:
	smtphost -- the smtp server to use. (default 'localhost')
	subject -- the email subject. (default '')
	attach -- file/directory name, or list of files and directories to attach. When a directory is supplied all files within are attached. (default None)
	recursive -- whether or not to recursively attach subdirectories when directories are supplied to attach. (default False)
	"""
	if isinstance(recipient, (str, unicode)): recipient = (recipient, )
	if isinstance(attach, (str, unicode)): attach = (attach,)
	if attach is None:
		msg = MIMEText(text)
	else:
		msg = MIMEMultipart()
		msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
		msg.attach(MIMEText(text))
		for attachment in attach:
			messages = _get_mime_msg(attachment, recursive=recursive)
			for _msg in messages:
				msg.attach(_msg)

	msg['From'] = sender
	msg['To'] = COMMASPACE.join(recipient)
	msg['Subject'] = subject
	server = smtplib.SMTP(smtphost)
	server.sendmail(sender, recipient, msg.as_string())
	server.quit()

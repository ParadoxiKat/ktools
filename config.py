# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Built-in Modules:
import argparse
import codecs
import collections
import json
import os.path
import threading

# Local Modules:
from .log import get_logging_parser
from .utils import get_program_path, get_settings_path

config_lock = threading.RLock()

class ConfigError(Exception):
	"""Config Error"""

def _valid_path(path, filename='config.json', must_exist=True, create=False):
	path = os.path.abspath(path) #be sure we have an absolute path
	exists = os.path.exists(path)
	if must_exist and not exists: raise ConfigError('file does not exist: {}'.format(path))
	if not exists: #assume path is a file
		dirname, filename = os.path.dirname(path), os.path.basename(path)
		if not os.path.exists(dirname): #parent directory doesn't exist
			if not create: raise ConfigError('Directory does not exist: {}'.format(dirname)) # so we can't create a file.
			else: os.makedirs(dirname) #so make it and all it's parents if necessary
		if not filename.lower().endswith('.json'): #Add .json file ext
			filename += '.json'
		path = os.path.join(dirname, filename)
	else: # path does exist
		if os.path.isdir(path): path = os.path.join(path, filename) # it's a directory, add the file name
		elif not os.path.isfile(path): raise ConfigError('Invalid path. Not a file or directory: {}'.format(path)) #it's not a file, die. Is a file falls through untouched.
	return path
			
		
		


def get_config_parser(parents=[]):
	parser=argparse.ArgumentParser(add_help=False, parents=parents)
	group = parser.add_argument_group(title='Configuration options', description='(Options are mutually exclusive.)')
	valid_path = lambda path:_valid_path(path, filename=self._defaultfilename) # because instance methods appear to not be hashable (???)
	xgroup = group.add_mutually_exclusive_group(required=False)
	xgroup.add_argument('-c', '--config-file', action='append', dest='configfilepath', type=valid_path, help='Path to additional config file to use. This option can be used multiple times to include multiple files. Only the last one given will be written to.')
	xgroup.add_argument('-C', '--1config-file', dest='configfilepath', type=valid_path, help='Path to config file to use. This option will use *ONLY* this file, discarding all others.')
	return parser

class Config(collections.MutableMapping):
	"""JSON config file parser
	
	Loads 1 or more json-formatted config files and presents them as a dictionary.
	
	Config(*files, defaultfilename='config.json')
	
	Files are loaded in order, left to right. If the path is a directory, defaultfilename is appended.
	Read opperations start from the last file loaded and work their way back. So keys present in later files override the same key from an earlier file.
	Write opperations only opperate on the final file given.
	"""

	def __init__(self, *args, **kwargs):
		super(Config, self).__init__()
		self.config_files = []
		self._defaultfilename = kwargs.pop('filename', 'config.json')
		self._args_excludes = set()
		arg_configs = kwargs.pop('arg_configs', False)
		args_as_keys = kwargs.pop('args_as_keys', False)
		parents = kwargs.pop('parents', [])
		parser = get_config_parser(parents=parents)
		self.args = None
		for path in args:
			self.config_files.append(_valid_path(path, filename=self._defaultfilename, must_exist=False, create=True))
		if arg_configs: self._get_arg_configs(parser)
		self._parser = parser
		self.reload()

	def __getitem__(self, key):
		return self._config[key]

	def __setitem__(self, key, value):
		if self.args is not None and hasattr(self.args, key): setattr(self.args, key, value)
		self._configs[-1][key] = value

	def __delitem__(self, key):
		if self.args is not None and hasattr(self.args, key): delattr(self.args, key)
		else: del self._configs[-1][key]

	def __iter__(self):
		return iter(self._config)

	def __len__(self):
		return len(self._config)

	@property
	def _config(self):
		d={}
		for c in self._configs: d.update(c)
		if self.args is not None: d.update(self.args._get_kwargs())
		return d

	def _get_arg_configs(self, parser):
		path = getattr(parser.parse_known_args()[0], 'configfilepath', None)
		if path is not None:
			if isinstance(path, str): self.config_files = [path]
			else: self.config_files += path
		if 'configfilepath' not in self._args_excludes: self._args_excludes.add('configfilepath')

	def _parse(self, file_name):
		if os.path.exists(file_name):
			if not os.path.isdir(file_name):
				try:
					with codecs.open(file_name, "rb", encoding="utf-8") as file_object:
						return json.load(file_object)
				except IOError as e:
					raise ConfigError("{}: '{}'".format(e.strerror, e.filename))
				except ValueError:
					raise ConfigError("Corrupted json file: {}".format(file_name))
			else:
				raise ConfigError("'{}' is a directory, not a file.".format(file_name))
		else:
			return {}

	def clear(self):
		return self._configs[-1].clear()

	def pop(self, *a, **kw):
		return self._configs[-1].pop(*a, **kw)

	def popitems(self, *a, **kw):
		return self._configs[-1].popitems(*a, **kw)

	def reload(self):
		self._configs = []
		print(self.config_files)
		for f in self.config_files: self._configs.append(self._parse(f))
		if self._parser is not None:
			args = self._parser.parse_known_args()[0]
			for x in self._args_excludes:
				if hasattr(args, x): delattr(args, x)
			self.args = args

	def save(self):
		with codecs.open(self.config_files[-1], "wb", encoding="utf-8") as file_object:
			json.dump(self._configs[-1], file_object, sort_keys=True, indent=2, separators=(",", ": "))

	def setdefault(self, *a, **kw):
		return self._configs[-1].setdefault(*a, **kw)

	def update(self, *a, **kw):
		return self._configs[-1].update(*a, **kw)
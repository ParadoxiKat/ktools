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
from .utils import get_program_path, get_settings_path

config_lock = threading.RLock()

class ConfigError(Exception):
	"""Config Error"""

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
		self._args_excludes = []
		parser = kwargs.pop('parser', None)
		arg_configs = kwargs.pop('arg_configs', False)
		args_as_keys = kwargs.pop('args_as_keys', False)
		if (arg_configs or args_as_keys) and parser is None: parser = argparse.ArgumentParser()
		self.args = None
		self._parser = parser
		for path in args:
			self.config_files.append(self._valid_path(path, existing=False))
		if arg_configs: self._get_arg_configs()
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
		group = parser.add_argument_group(title='Configuration options', description='(Options are mutually exclusive.)')
		xgroup = group.add_mutually_exclusive_group(required=False)
		valid_path = lambda path:self._valid_path(path) # because instance methods appear to not be hashable (???)
		xgroup.add_argument('-c', '--config-file', action='append', dest='configfilepath', type=valid_path, help='Path to additional config file to use. This option can be used multiple times to include multiple files. Only the last one given will be written to.')
		xgroup.add_argument('-C', '--1config-file', dest='configfilepath', type=valid_path, help='Path to config file to use. This option will use *ONLY* this file, discarding all others.')
		path = parser.parse_known_args()[0].configfilepath
		if path is not None:
			if isinstance(path, str): self.config_files = [path]
			else: self.config_files += path
		if 'configfilepath' not in self._args_excludes: self._args_excludes.append('configfilepath')

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

	def _valid_path(self, path, existing=True):
		if not os.path.isabs(path): path = os.path.abspath(path)
		if os.path.isdir(path): path = os.path.join(path, self._defaultfilename)
		if os.path.exists(path):
			if os.path.isfile(path): return path
			elif os.path.isdir(path): raise ConfigError('{} is a directory.'.format(path))
			else: raise ConfigError('{} exists, but is not a file.'.format(path))
		else:
			if not existing and os.path.isdir(os.path.dirname(path)): return path
			else: raise ConfigError('Path does not exist: {}'.format(path))

	def clear(self):
		return self._configs[-1].clear()

	def pop(self, *a, **kw):
		return self._configs[-1].pop(*a, **kw)

	def popitems(self, *a, **kw):
		return self._configs[-1].popitems(*a, **kw)

	def reload(self):
		self._configs = []
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
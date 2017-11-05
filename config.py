# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Built-in Modules:
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
		for path in args:
			path = os.path.abspath(path)
			if os.path.exists(path):
				if os.path.isdir(path): self.config_files.append(os.path.join(path, self._defaultfilename))
				elif os.path.isfile(path): self.config_files.append(path)
			else:
				if os.path.isdir(os.path.dirname(path)): self.config_files.append(path)
		if not self.config_files: self.config_files.append(os.path.join(os.getcwd(), self._defaultfilename))
		self.reload()

	@property
	def _config(self):
		d={}
		for c in self._configs: d.update(c)
		return d

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

	def __getitem__(self, key):
		return self._config[key]

	def __setitem__(self, key, value):
		self._configs[-1][key] = value

	def __delitem__(self, key):
		del self._configs[-1][key]

	def __iter__(self):
		return iter(self._config)

	def __len__(self):
		return len(self._config)
	def clear(self):
		return self._configs[-1].clear()

	def pop(self, *a, **kw):
		return self._configs[-1].pop(*a, **kw)

	def popitems(self, *a, **kw):
		return self._configs[-1].popitems(*a, **kw)

	def reload(self):
		self._configs = []
		for f in self.config_files: self._configs.append(self._parse(f))

	def save(self):
		with codecs.open(self.config_files[-1], "wb", encoding="utf-8") as file_object:
			json.dump(self._configs[-1], file_object, sort_keys=True, indent=2, separators=(",", ": "))

	def setdefault(self, *a, **kw):
		return self._configs[-1].setdefault(*a, **kw)

	def update(self, *a, **kw):
		return self._configs[-1].update(*a, **kw)
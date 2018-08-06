# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import, annotations, division, print_function

import bz2
import codecs
import hashlib
import io
# On python2, backports.lzma must be installed.
try: import lzma
except ImportError as e: lzma = None
import os.path
import struct
import zlib

# pynacl is optional, attempt to import all it's relevant sub packages.
try:
	import nacl.bindings
	import nacl.hash
	import nacl.public
	import nacl.pwhash
	import nacl.secret
	import nacl.signing
	import nacl.utils
except ImportError as e:
	nacl = None


class Datafile(object):
	"""A file-like object that can encode/compress/encrypt/hash/sign data.
	
	All data is stored in-memory, thus supporting of large files is likely problematic.
	Encryption, signing, and some hash functions  require pynacl to be installed.
	lzma compression support on python2 requires backports.lzma package.
	<add argument docs here>
	"""

	_io_obj = None

	def __init__(self, filename=None, initial_value=None, newline=None, 
			encode=False, encoding_type=None,
			compress=False, compression_level=-1,
			encrypt=False, encryption_key=None
			):
		if filename is None:
			self.filename = filename
		else:
			self.filename = os.path.abspath(filename)
		self.encode = encode		
		self.encoding_type= encoding_type
		self.compress = compress
		self.compression_level = compression_level
		self.encrypt = encrypt
		self.encryption_key = encryption_key
		self._make_io_obj(initial_value=initial_value, newline=newline)

	def __getattribute__(self, attr):
		try:
			return super(Datafile, self).__getattribute__(attr)
		except AttributeError as e:
			# Pass failed lookups to the underlying _io_obj
			# We don't want to lookup methods of _io_obj that start with '_'.
			_attr = None if attr.startswith('_') else getattr(self._io_obj, attr, None)
			if _attr is None:
				raise
			return _attr

	def _make_io_obj(self, initial_value=None, newline=None):
		# Create io object for internal use based on encoding settings.
		if self.encode:
			if initial_value is None: initial_value = u''
			if newline is None: newline = u'\n'
			self._io_obj = io.StringIO(initial_value=initial_value, newline=newline)
			self._io_obj.newlines = newline
		else:
			if initial_value is None: initial_value = b''
			self._io_obj = io.BytesIO(initial_bytes=initial_value)

	def _readfile(self, filename):
		"""Attempt to open the specified file and return it's contents
		
		If it fails, attempt to create necessary directories and the file and return an empty string.
		"""
		try: f=open(filename, 'rb')
		except PermissionError as e:
			if os.path.isdir(filename): raise ValueError('{} is a directory.'.format(filename))
			else: raise e
		except FileNotFoundError as e:
			# Path exists, file doesn't. Create and retry.
			self._writefile(filename, b'')
			return self._readfile(filename)
		except exception as e: raise e
		data = f.read()
		f.close()
		return data

	def _writefile(self, filename, data):
		"""Write the data to a file
		
		Create file and missing directories if needed.
		"""
		try: f=open(filename, 'wb')
		except FileNotFoundError as e:
			dirname = os.path.dirname(filename)
			if os.path.isfile(dirname): raise ValueError("{} isn't a directory!")
			if not os.path.exists(dirname): os.makedirs(dirname)
			f = open(filename, 'wb')
		except Exception as e: raise e
		f.write(data)
		f.close()

	def load(self, encryption_key=None, *args):
		if len(args) >1: raise TypeError('load() takes 1 or 2 positional arguments but {} were given'.format(len(args)+1))
		if self.filename is None and not args: raise ValueError('No file name associated with this Datafile object and no file name supplied to load().')
		if args: self.filename, filename = args[0]
		else: filename = self.filename
		data = self._readfile(filename)
		if self.encrypt:
			if nacl is None:
				self.encrypt = False
				import warnings
				warnings.warn("Encryption specified, but pynacl is not installed. Disabling encryption.")
			# Look for the encryption key
			encryption_key = encryption_key or self.encryption_key or os.environ.get('encryption_key', None)
			# Disable encryption if no key found.
			if encryption_key is None: raise RunTimeError('Encryption specified for {}, but no key was found.'.format(filename))
			# Create the secret box for encryption/decryption
			box = nacl.secret.SecretBox(encryption_key)
			# Try and decrypt data using our key.
			data = box.decrypt(data)
		if self.compress:
			data = zlib.decompress(data)
		if self.encode:
			data = codecs.decode(data, self.encoding_type)
		# Now data has been read from disk, decrypted, decompressed, and restored to it's encoding.
		# Load it into the StringIO buffer, overwriting previous data
		self.seek(0) # rewind to start of file
		self.truncate() # delete contents
		self.write(data) # Fill with our new data
		self.seek(0) # Rewind to beginning again

	def save(self, filename=None, encryption_key=None):
		data = self.getvalue()
		if self.encode:
			data = codecs.encode(data, self.encoding_type)
		if self.compress:
			data = zlib.compress(data, self.compression_level)
		if self.encrypt:
			if nacl is None:
				self.encrypt = False
				import warnings
				warnings.warn("Encryption specified, but pynacl is not installed. Disabling encryption.")
			# Look for the encryption key
			encryption_key = encryption_key or self.encryption_key or os.environ.get('encryption_key', None)
			# disable encryption if no key found.
			if encryption_key is None: raise RunTimeError('Encryption specified for {}, but no key was found.'.format(filename))
			# Create secret box for encryption/decryption.
			box = nacl.secret.SecretBox(encryption_key)
			# Encrypt data with the key.
			data = box.encrypt(data)
		# Data has been encoded, compressed, and encrypted. Save to file.
		filename = filename or self.filename
		self._writefile(filename, data)



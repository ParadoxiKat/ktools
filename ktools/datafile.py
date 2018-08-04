from __future__ import print_function
import codecs
try: import cryptography.fernet
except ImportError as e: cryptography = None
import io
import os.path
import zlib

class DataFile(io.StringIO):
	"""Data file object that can transparently encode/compress/encrypt data.
	
	All data is stored in-memory, thus supporting of large files is likely problematic.
	Compression requires cryptography to be installed."""

	def __init__(self, filename=None, initial_value=u'', newline='\n', encode=True, encoding_type='utf-8', compress=False, compression_level=-1, encrypt=False, encryption_key=None):
		# Init the underlying StringIO object.
		super(DataFile, self).__init__(initial_value=initial_value, newline=newline)
		# Save the other attributes
		if filename is None: self.filename = filename
		else: self.filename = os.path.abspath(filename)
		self.encode = encode		
		self.encoding_type= encoding_type
		self.compress = compress
		self.compression_level = compression_level
		self.encrypt = encrypt
		self.encryption_key = encryption_key

	def _readfile(self, filename):
		"""Attempt to open the specified file and return it's contents
		
		If it fails, attempt to create necessary directories and the file and return an empty string."""
		try: f=open(filename, 'rb')
		except PermissionError as e:
			if os.path.isdir(filename): raise ValueError('{} is a directory.'.format(filename))
			else: raise e
		except FileNotFoundError as e:
			self._writefile(filename, b'')
			return self._readfile(filename)
		except exception as e: raise e
		data = f.read()
		f.close()
		return data

	def _writefile(self, filename, data):
		"""Write the data to a file
		
		Create file and missing directories if needed."""
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
		if self.filename is None and not args: raise ValueError('No file name associated with this DataFile object and no file name supplied to load().')
		if args: self.filename, filename = args[0]
		else: filename = self.filename
		data = self._readfile(filename)
		if self.encrypt:
			if cryptography is None:
				self.encrypt = False
				import warnings
				warnings.warn("Encryption specified, but cryptography is not installed. Disabling encryption.")
			encryption_key = encryption_key or self.encryption_key or os.environ.get('encryption_key', None)
			if encryption_key is None: raise RunTimeError('Encryption specified for {}, but no key was found.'.format(filename))
			fernet = cryptography.fernet.Fernet(encryption_key)
			data = fernet.decrypt(data)
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
			if cryptography is None:
				self.encrypt = False
				import warnings
				warnings.warn("Encryption specified, but cryptography is not installed. Disabling encryption.")
			encryption_key = encryption_key or self.encryption_key or os.environ.get('encryption_key', None)
			if encryption_key is None: raise RunTimeError('Encryption specified for {}, but no key was found.'.format(filename))
			fernet = cryptography.fernet.Fernet(encryption_key)
			data = fernet.encrypt(data)
		# Data has been encoded, compressed, and encrypted. Save to file.
		filename = filename or self.filename
		self._writefile(filename, data)



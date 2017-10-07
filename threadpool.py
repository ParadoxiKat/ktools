# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Implements a simple threadpool."""

from __future__ import division, print_function
import logging
try:
	import Queue as queue
except ImportError:
	import queue
import threading
from types import GeneratorType

# Monkey patch range with xrange in Python2.
try:
	_range, range = range, xrange
except NameError:
	pass

logger=logging.getLogger(__name__)

class ThreadPoolDying(Exception):
	"""raised when insert_task or insert_tasks is called on a dying pool"""

class ThreadPool(object):
	"""A dynamic thread pool to handle any data type."""
	def __init__(self, num_threads=5, setup=None, cleanup=None, start=False):
		"""num_threads should be an int (defaults to 5 
		if not supplied).
		"""
		logger.debug('New ThreadPool "{}".'.format(self))
		self.tasks_queue = queue.Queue(maxsize=num_threads*2+1)
		self.dying = False
		self._resize_lock = threading.Lock()
		self.setup = setup
		self.cleanup = cleanup
		self._threads = set()
		for x in range(num_threads): self._newthread(self.tasks_queue)
		if start: self.start()

	def __enter__(self):
		if not self.size: raise RuntimeError("Can't enter an empty pool!")
		logger.debug('Entering {}.'.format(self))
		if not self.started: self.start()
		return self

	def __exit__(self, etype, val, tb):
		logger.debug('Exiting {} with "{}, {}, {}".'.format(self, etype, val, tb))
		if etype is None or etype is KeyboardInterrupt: self.stop()
		else:
			self.stop(finish=False)
			raise etype, val, tb

	@property
	def alive(self):
		return bool(self.size)

	@alive.setter
	def alive(self, value):
		val = bool(value)
		if self.alive and not val: self.stop()
		elif self.alive == val: return
		else:
			self.dying = False
			self.size = int(value)

	@property
	def size(self):
		return len(self._threads)

	@size.setter
	def size(self, value):
		self.set_thread_count(value)

	@property
	def started(self):
		if self.size == 0: return False
		_all = all(_.isAlive() for _ in self._threads)
		_any = any(_.isAlive() for _ in self._threads)
		if any and not all:
			for thread in _threads:
				if not thread.isAlive(): thread.start()
		return _any

	@property
	def _firstid(self):
		ids={thread.id for thread in self._threads}
		size = self.size
		for n in range(1, size+1 ):
			if n not in ids: return n
		else: return size+1

	def _newthread(self, queue, timeout=0.5):
		if self.dying: return
		new_thread = _WorkerThread(self, queue, timeout=timeout)
		if callable(self.setup): self.setup(new_thread)
		if self.started: new_thread.start()
		self._threads.add(new_thread)

	def _insert_task(self, new_task):
		logger.debug('Putting {} in tasks queue.'.format(new_task))
		self.tasks_queue.put(new_task)

	def insert_task(self, new_task):
		"""
		insert a new task into the queue.
		"""
		logger.debug("Received {}.".format(new_task))
		if self.alive and not self.dying:
			#we're alive, so we can take new tasks
			self._insert_task(new_task)
		else: #self.alive is True, we can't take new tasks
			raise ThreadPoolDying

	def insert_tasks(self, new_tasks):
		"""
		insert a group of new tasks into the queue.
		"""
		new_tasks = iter(new_tasks)
		inserted = 0
		while self.alive and not self.dying: #we're alive, so we can take new tasks
			try:
				self._insert_task(next(new_tasks))
				inserted += 1
			except StopIteration: break
		else:
			#alive is False, we can't take new tasks
			raise ThreadPoolDying
		unfinished = len(tuple(tasks))
		if unfinished: numtasks = '{} of {}'.format(inserted, inserted+unfinished)
		else: numtasks=str(inserted)
		logger.debug("Inserted {} tasks.".format(numtasks))
		if unfinished: raise ThreadPoolDying

	def set_thread_count(self, n):
		"""
		set_thread_count(n)
		Set number of threads to n. If n is 0, kill all threads in the pool.
		"""
		if isinstance(n,int):
			#Taking anything but an int here would just be silly!
			with self._resize_lock:
				#Obtain _resize_lock so no one else can resize at the same time
				if n < 0: n = 0 # get rid of negative numbers
				if n == 0:
					for x in range(self.size):
						self._insert_task(None)
				elif n == len(self._threads):
					#we don't need to do anything...
					return
				elif n > len(self._threads):
					#create new threads, start them, and add them to the pool.
					for x in range(n-len(self._threads)): self._newthread(self.tasks_queue)
				else:
					#Put None into the queue for each thread we want to get rid of.
					for x in range(self.size-n):
						self._insert_task(None)
		else:
			raiseTypeError('N must be an int!')

	def start(self):
		if self.started: return # already started
		if self.size == 0: return #nothing to start
		started = 0
		for thread in self._threads:
			if not thread.isAlive():
				thread.start()
				started += 1
		logger.debug("Started {} threads.".format(started))

	def stop(self, wait=True, finish=True):
		if self.dying or not self.started: return # stop has already been called, or no threads have been started.
		self.dying = True
		if finish:
			#We should let the threads finish up the tasks in the queue, then shut down.
			#receiving None as a task causes a thread to terminate
			#setting self.size to 0 causes None to be put into the queue for each thread.
			self.size = 0
			#self.alive = False
			if wait: #block until all tasks are done
				if not self.tasks_queue.empty(): self.tasks_queue.join()
			else: #daemonize threads and let them finish up the queue on their own.
				for thread in self._threads.copy(): thread.setDaemon(True)
		else:
			#threads should not finish tasks in the queue, die immediately after this iteration
			for thread in self._threads.copy(): thread.stop()
			#empty the queue:
			while not self.tasks_queue.empty():
				_ = q.get()
				self.tasks_queue.task_done()

	def stop_thread(self, thread):
		thread.alive = False
		if callable(self.cleanup): self.cleanup(thread)
		try: self._threads.remove(thread)
		except KeyError: pass

class _WorkerThread(threading.Thread):
	"""Worker thread for use by the threadpool only!"""
	def __init__(self, pool, tasks_queue, timeout=0.5):
		self.alive=True
		self.id = pool._firstid
		self.pool=pool
		self.tasks_queue = tasks_queue
		self.timeout = timeout
		threading.Thread.__init__(self)
		self.name = "Worker thread{}".format(self.id)
		logger.debug('New thread "{}".'.format(self.name))
		self.args = []
		self.kwargs = {}
		self.callback = None

	def process_task(self, task):
		logger.debug("{} processing task {}.".format(self.name, task))
		if task is None:
			self.stop()
			return
		callback = None
		if isinstance(task, GeneratorType):
			callback = task.send
			task = task.next()
		if callable(task): func, args, kwargs, callback = task, self.args, self.kwargs, lambda x:None
		elif isinstance(task, (list, tuple)):
			func = task[0]
			try: args = task[1]
			except IndexError: args = []
			try: kwargs = task[2]
			except IndexError: kwargs = {}
			try: callback = task[3]
			except IndexError: callback = callback
		if callback is None: callback = lambda x:None
		args += type(args)(self.args)
		_kwargs = self.kwargs
		_kwargs.update(kwargs)
		kwargs = _kwargs
		del _kwargs
		try:
			logger.debug("{}: Calling {} with args {} and kwargs {}.".format(self.name, func, args, kwargs))
			result = func(*args, **kwargs)
			logger.debug('{}: {} returned "{}".'.format(self.name, func, result))
		except:
			logger.exception('{} raised an exception:'.format(func))
			result = sys.exc_info()
		finally:
			logger.debug("Calling callback {} with result {}.".format(callback, result))
			callback(result)

	def run(self):
		logger.debug("{} starting".format(self.name))
		#self.alive determines when this thread should die. pool.alive determines when all threads should die.
		#self.alive is set to false when None is received as a task.
		try:
			while self.alive:
				try:
					task = self.tasks_queue.get(timeout=self.timeout)
					logger.debug('Received task: "{}"'.format(task))
				except queue.Empty:
					continue
				self.process_task(task)
				self.tasks_queue.task_done()
		except:
			logger.exception('Unhandled error')
		finally:
			logger.debug('{}: loop exiting.'.format(self.name))
		self.stop()

	def stop(self):
		self.pool.stop_thread(self)


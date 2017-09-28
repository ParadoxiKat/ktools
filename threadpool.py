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

# Monkey patch range with xrange in Python2.
try:
	_range, range = range, xrange
except NameError:
	pass

logger=logging.getLogger(__name__)

class ThreadPool(object):
	"""A dynamic thread pool to handle any data type."""
	def __init__(self, num_threads=5, setup=None, cleanup=None):
		"""num_threads should be an int (defaults to 5 
		if not supplied).
		"""
		self.tasks_queue = queue.Queue()
		self.tasks_lock = threading.Condition(threading.Lock())
		self._resize_lock = threading.Condition(threading.Lock())
		self.setup = setup
		self.cleanup = cleanup
		self._threads = set()
		for x in range(num_threads): self._newthread(self.tasks_queue, self.tasks_lock)

	@property
	def alive(self):
		return bool(self.size)

	@alive.setter
	def alive(self, value):
		value = bool(value)
		if self.alive and not value: self.size=0
		elif self.alive == value: return
		self.size=1

	@property
	def size(self):
		return len(self._threads)

	@size.setter
	def size(self, value):
		self.set_thread_count(value)

	@property
	def _firstid(self):
		ids={thread.id for thread in self._threads}
		size = self.size
		for n in range(1, size+1 ):
			if n not in ids: return n
		else: return size+1

	def _newthread(self, queue, lock):
		new_thread = _WorkerThread(self, queue, lock)
		if callable(self.setup): self.setup(new_thread)
		new_thread.start()
		self._threads.add(new_thread)

	def _insert_task(self, new_task):
		logger.debug('Putting {} in tasks queue.'.format(new_task))
		self.tasks_queue.put(new_task)

	def insert_task(self, new_task):
		"""
		insert a new task into the queue.
		"""
		logger.debug("Received {}.".format(new_task))
		if self.alive:
			#we're alive, so we can take new tasks
			with self.tasks_lock: #Obtain tasks_lock so we can notify threads 
				self._insert_task(new_task)
				#If any threads are sleeping, wake one up to handle the task.
				self.tasks_lock.notify()
		else: #self.alive is True, we can't take new tasks
			raiseIOError('The pool has been shut down!')

	def insert_tasks(self, new_tasks):
		"""
		insert a group of new tasks into the queue.
		"""
		new_tasks = tuple(new_tasks)
		num_tasks = len(new_tasks)
		logger.debug("Received {} new tasks.".format(num_tasks))
		if self.alive: #we're alive, so we can take new tasks
			with self.tasks_lock: #Obtain tasks_lock so we can notify threads 
				for new_task in new_tasks:
					self._insert_task(new_task)
				#If any threads are sleeping, wake them up to handle the task.
				#If we have more (or the same) number of jobs as threads
				if num_tasks >= self.size: self.tasks_lock.notifyAll()
				#If we have more threads than tasks, only wake up enough threads to handle the tasks
				else: self.tasks_lock.notify(n=num_tasks)
		else:
			#alive is False, we can't take new tasks
			raise IOError('The pool is shutting down!')


	def set_thread_count(self, n):
		"""
		set_thread_count(n)
		Set number of threads to n. If n is 0, kill all threads in the pool.
		"""
		if isinstance(n,int):
			#Taking anything but an int here would just be silly!
			with self._resize_lock:
				#Obtain _resize_lock so no one else can resize at the same time
				if n == 0:
					self.insert_tasks((None,)*self.size)
				elif n == len(self._threads):
					#we don't need to do anything...
					return
				elif n > len(self._threads):
					#create new threads,start them, and add them to the pool.
					for x in range(n-len(self._threads)): self._newthread(self.tasks_queue, self.tasks_lock)
				else:
					#Put None into the queue for each thread we want to get rid of.
					for x in range(len(self._threads)-n):
						self.insert_task(None)
		else:
			raiseTypeError('N must be an int!')

	def stop_thread(self, thread):
		thread.alive = False
		if callable(self.cleanup): self.cleanup(thread)
		try: self._threads.remove(thread)
		except KeyError: pass

class _WorkerThread(threading.Thread):
	"""Worker thread for use by the threadpool only!"""
	def __init__(self, pool, tasks_queue, tasks_lock, res_queue=None, res_lock=None):
		self.alive=True
		self.id = pool._firstid
		self.pool=pool
		self.tasks_queue = tasks_queue
		self.tasks_lock = tasks_lock
		self.res_queue = res_queue
		self.res_lock = res_lock or tasks_lock
		threading.Thread.__init__(self)
		self.name = "Worker thread{}".format(self.id)
		self.args = []
		self.kwargs = {}

	def get_task(self):
		#Obtain tasks_lock so nobody else messes with the queue.
		with self.tasks_lock:
			logger.debug("{}: acquired tasks_lock.".format(self.name))
			if self.tasks_queue.empty():
				#Wait until something is available.
				logger.debug("{}: no tasks. Going to sleep.".format(self.name))
				self.tasks_lock.wait()
			logger.debug("{}: waking up!".format(self.name))
			task = self.tasks_queue.get(block=False)
			logger.debug("{}: Received {}.".format(self.name, task))
			return task

	def process_task(self, task):
		logger.debug("{} processing task {}.".format(self.name, task))
		if task is None:
			self.stop()
			return
		if callable(task): func, task = task, {}
		func = task['func']
		args = task.get('args', ()) + self.args
		kwargs = task.get('kwargs', {})
		kwargs.update(self.kwargs)
		try:
			logger.debug("{}: Calling {} with args {} and kwargs {}.".format(self.name, func, args, kwargs))
			result = func(*args, **kwargs)
			logger.debug('{}: {} returned "{}".'.format(self.name, func, result))
		except:
			logger.exception('{} raised an exception:'.format(func))
			if not hasattr(task, 'exc_handler'): result = None
			else:
				exc_info = sys.exc_info()
				if callable(exc_handler):
					logger.debug('{}: Trying provided exception handler {}.'.format(self.name, exc_handler))
					result = exc_handler(args, kwargs, exc_info)
					logger.debug('{}: Exception handler {} returned "{}"'.format(self.name, result))
				else:
					logger.debug('{}: No exception handler provided, returning exc_info'.format(self.name))
					result = exc_info
		finally:
			if result is not None and self.res_queue is not None:
				with self.res_lock:
					self.res_queue.put(result)

	def run(self):
		logger.debug("{} starting".format(self.name))
		#self.alive determines when this thread should die. pool.alive determines when all threads should die.
		#self.alive is set to false when None is received as a task.
		try:
			while self.alive and self.pool.alive:
				try:
					task = self.get_task()
				except queue.Empty:
					logger.debug("{}: no tasks left!".format(self.name))
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


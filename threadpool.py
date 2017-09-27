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
	def __init__(self, num_threads=5):
		"""num_threads should be an int (defaults to 5 
		if not supplied).
		"""
		#set the number of items the queue can hold to 5 times the threadcount
		#I don't know why.
		self.tasks_queue = queue.Queue(num_threads*5)
		self.tasks_lock = threading.Condition(threading.Lock())
		self._resize_lock = threading.Condition(threading.Lock())
		self.alive = True
		self._threads = set()
		for x in range(num_threads):
			new_thread = _WorkerThread(self, self.tasks_queue, self.tasks_lock)
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
		if not self._is_dying:
			#we're alive, so we can take new tasks
			with self._tasks_lock: #Obtain _tasks_lock so we can notify threads 
				self._insert_task(new_task)
			#If any threads are sleeping, wake one up to handle the task.
			self._tasks_lock.notify()
		else: #self.alive is True, we can't take new tasks
			raiseIOError('The pool has been shut down!')

	def insert_tasks(self, new_tasks):
		"""
		insert a group of new tasks into the queue.
		"""
		logger.debug("Received {} new tasks.".format(len(tuple(new_tasks))))
		if not self.alive: #we're alive, so we can take new tasks
			with self._tasks_lock: #Obtain _tasks_lock so we can notify threads 
				for new_task in new_tasks:
					self._insert_task(new_task)
			#If any threads are sleeping, wake them up to handle the task.
			self._tasks_lock.notifyAll()
		else:
			#_is_dying is True, we can't take new tasks
			raiseIOError('The pool is shutting down!')

	def _get_task(self):
		"""
		FOR INTERNAL USE ONLY!!!
		Gets and returns an item from the queue, for use by worker threads.
		"""
		with self.tasks_lock:
			task = self._tasks.get()
		return task

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
					#set _is_dying to True so threads stop working on tasks,
					#and insert_task rejects them. 
					self._is_dying=True
					with self._tasks_lock:
						#Obtain _tasks_lock so we can notify all
						for x in range(len(self._threads)):
							#Put None into the queue for every thread.
							#Receiving None causes a thread to exit and remove itself from the pool.
							self._tasks.put(None)
						#Notify all sleeping threads of insertion
						self._tasks_lock.notifyAll()
				elif n == len(self._threads):
					#we don't need to do anything...
					return
				elif n > len(self._threads):
					#create new threads,start them, and add them to the pool.
					for x in range(n-len(self._threads)):
						new_thread=_WorkerThread(self, self._task_handler)
						new_thread.start()
						self._threads.add(new_thread)
				else:
					#Put None into the queue for each thread we want to get rid of.
					for x in range(len(self._threads)-n):
						with self._tasks_lock:
							#Obtain lock so we can notify a thread to kill
							self._tasks.put(None)
							self._tasks_lock.notify()
		else:
			raiseTypeError('N must be an int!')

class _WorkerThread(threading.Thread):
	"""Worker thread for use by the threadpool only!"""
	def __init__(self, pool, tasks_queue, tasks_lock, res_queue=None, res_lock=None):
		self.alive=True
		self.pool=pool
		self.tasks_queue = tasks_queue
		self.tasks_lock = tasks_lock
		self.res_queue = res_queue
		self.res_lock = res_lock or tasks_lock
		threading.Thread.__init__(self)

	def process_task(self, task):
		if callable(task): func, task = task, {}
		func = task['func']
		args = task.get('args', ())
		kwargs = task.get('kwargs', {})
		try:
			logger.debug("Calling {} with args {} and kwargs {}.".format(func, args, kwargs))
			result = func(*args, **kwargs)
			logger.debug('{} returned "{}".'.format(func, result))
		except:
			logger.exception('{} raised an exception:'.format(func))
			if not hasattr(task, 'exc_handler'): result = None
			else:
				exc_info = sys.exc_info()
				if callable(exc_handler):
					logger.debug('Trying provided exception handler {}.'.format(exc_handler))
					result = exc_handler(args, kwargs, exc_info)
					logger.debug('Exception handler {} returned "{}"'.format(result))
				else:
					logger.debug('No exception handler provided, returning exc_info')
					result = exc_info
		finally:
			if result is not None and self.res_queue is not None:
				with self.res_lock:
					self.res_queue.put(result)
			self.tasks_queue.task_done()

	def run(self):
		logger.debug("{} starting".format(self.getName()))
		#self.alive determines when this thread should die. pool.alive determines when all threads should die.
		#self.alive is set to false when None is received as a task.
		try:
			while self.alive and self.pool.alive:
				#Obtain _tasks_lock so nobody else messes with the queue.
				with self.tasks_lock:
					logger.debug("{}: acquired tasks_lock.".format(self.getName()))
					if self.tasks_queue.empty():
						#Wait until something is available.
						logger.debug("{}: no tasks. Going to sleep.".format(self.getName()))
						self.tasks_lock.wait()
						logger.debug("{}: waking up!".format(self.getName()))
					task=self.pool._get_task()
					logger.debug("Received {}.".format(task))
				if task is None: break
				logger.debug("{} processing task {}.".format(self.getName(), task))
				self.process_task(task)
		except:
			logger.exception('Unhandled error')
		finally:
			logger.debug('{} loop exiting.'.format(self.name))
		self.stop()

	def stop(self):
		if self.alive:
			logger.debug("{} dying.".format(self.getName()))
		try: self.pool._threads.remove(self)
		except KeyError: pass


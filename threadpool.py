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
	def __init__(self, task_handler, num_threads=5, valid_types=()):
		"""argument task_handler should be a callable and num_threads an int (defaults to 5 
		if not supplied). valid_types is a tuple of types that can be put into the queue. If left empty 
		all types are accepted (this is the default).
		"""
		self._task_handler=task_handler
		#set the number of items the queue can hold to 5 times the threadcount
		#I don't know why.
		self._tasks=queue.queue(num_threads*5)
		self._valid_types=valid_types
		self._tasks_lock=threading.Condition(threading.Lock())
		self._resize_lock=threading.Condition(threading.Lock())
		self._is_dying=False
		self._threads=set()
		for x in range(num_threads):
			new_thread=_WorkerThread(self)
			new_thread.start()
			self._threads.add(new_thread)

	def insert_task(self, new_task):
		"""
		insert a new task into the queue. If self._valid_types is empty, all types are accepted. 
		Otherwise, the type of new_task must be in self._valid_types.
		"""
		logger.debug("Received {}.".format(new_task))
		if not self._is_dying:
			#we're alive, so we can take new tasks
			if not self._valid_types or isinstance(new_task , self._valid_types):
				#Either _valid_types is empty or the type of our task is contained in it, so its valid
				with self._tasks_lock:
					#Obtain _tasks_lock so we can notify threads 
					logger.debug('Putting {} in tasks queue.'.format(new_task))
					self._tasks.put(new_task)
					#If any threads are sleeping, wake one up to handle the task.
					self._tasks_lock.notify()
			else:
				#the type of our task is not in _valid_types
				raiseTypeError('invalid type!')
		else:
			#_is_dying is True, we can't take new tasks
			raiseIOError('The pool is shutting down!')

	def _get_task(self):
		"""
		FOR INTERNAL USE ONLY!!!
		Gets and returns an item from the queue, for use by worker threads.
		"""
		return self._tasks.get()

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
	def __init__(self, pool):
		#hang onto the pool object so we can check the queue and other things
		self._pool=pool
		self._alive=True
		threading.Thread.__init__(self)

	@property
	def _task_handler(self):
		if not self._alive or self._pool._is_dying: return lambda *a, **kw:None
		return self._pool._task_handler

	def run(self):
		logger.debug("{} starting".format(self.getName()))
		#If self._pool._is_dying is True all threads die, if self._alive is false this thread dies.
		while self._alive and not self._pool._is_dying:
			#Obtain _tasks_lock so nobody else messes with the queue.
			with self._pool._tasks_lock:
				logger.debug("{} acquired lock. Waiting.".format(self.getName()))
				if self._pool._tasks.empty():
					#Wait until something is available.
					self._pool._tasks_lock.wait()
					logger.debug("{} waking up!".format(self.getName()))
				task=self._pool._get_task()
				self._pool._tasks.task_done()
				logger.debug("Received {}.".format(task))
			#If task is none we remove self from the _threads set, break the loop and die.
			if task is None:
				self._alive=False
				logger.debug("{} dying.".format(self.getName()))
				self._pool._threads.remove(self)
				break
			else: #Do our job and call task_handler with task!
				logger.debug("{} processing task {}.".format(self.getName(), task))
				self._task_handler(self, self._pool, task)


#
# asyn.scan - asyn pluggable scanners.
#
# A Scanner is an object implementing the informal scanner protocol:
#	remains = scan(self, buffer, callout)
# This should examine the data bytes in buffer (a basestring) and decide
# whether a leading substring thereof warrants processing. If it does,
# call the standard-form callout method
#	callout(ctx, <whatever>)
# where <whatever> is any number of positional arguments representing the match,
# and return the remaining part of buffer (empty string if all was matched).
# If the data warrants no processing (perhaps yet), return None.
#
# Copyright 2010-2016 Perry The Cynic. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
DEBUG = None

import re

from asyn.core import Context


#
# Base (mix-in) class for objects that feed a Scanner.
#
RAW = Context('RAW')		# canonical raw data delivery context

class Scannable(object):
	""" A mix-in class that parses and delivers data based on scanning classes.

		Scannable must be mixed-in to a subclass of Callable. Scannable maintains
		a read buffer fed through self._scan(data). Each _scan call attempts to deliver
		data downstream through the current self.scan object (or as a 'RAW' callout
		if scan is None). If scan reports no further progress, the remaining buffer
		data is retained for the next _scan call. It is up to the scanner to discard
		invalid or unexpected data from the buffer by consuming it.
	"""
	def __init__(self):
		self.scan = None
		self._rbuf = ''

	def _scan(self, data):
		""" Repeatedly generate scan events until we can't make any more progress.

			If self.scan is ever None, deliver (the rest of) the data as a RAW callout.
		"""
		self._rbuf += data
		while self._rbuf:
			if self.scan is None:
				self.callout(RAW, self._rbuf)
				self._rbuf = ''
				return
			result = self.scan.scan(self._rbuf, self.callout)
			if result is None:
				return
			if self._rbuf:	# was not flushed
				self._rbuf = result

	def _flush_scan(self):
		self._rbuf = ''


#
# A Scanner based on a vector of regex rules.
#
class Regex(object):
	""" A Scanner object based on a vector of regular expression matching rules.

		Regex implements a Scanner based on a list of (regex, state) pairs.
		The buffer is scanned by trying each regex in order; the first match wins.
		If no regex matches, the scan fails.

		There is no implicit mechanism for skipping bytes that won't or can't match
		any of our regex rules. If you want to recover from unexpected input, you
		must have a rule that does so.
	"""

	def __init__(self, ruleset, options=0):
		""" Initialize with optional rules. """
		self._rules = [(re.compile(rule[0], options),) + rule[1:] for rule in ruleset]

	def scan(self, buffer, callout):
		""" Try to match the buffer against our ruleset and callout a match.

			The first matching regex wins. We construct a Context from the rule's
			state value and attach the regex match object as ctx.match.
			All match groups in the winning regex become additional arguments
			passed to the callout.

			A rule with a false state suppresses the callout but still consumes its match
			in the buffer. Use this for whitespace consumption and recovery rules without
			bothering the callout recipients.

			Any values in a matching tuple beyond the second are assigned to the 'aux'
			field of the context. Aux is not set if there are only the regex and state.
		"""
		if DEBUG: DEBUG("scanning", repr(buffer))
		if buffer:
			for rule in self._rules:
				if DEBUG: DEBUG(" trying", *rule)
				pattern = rule[0]
				state = rule[1]
				m = pattern.match(buffer)
				if m:
					remains = buffer[m.end(0):]
					if DEBUG: DEBUG(" matched", repr(buffer[:m.end(0)]), "|", repr(remains))
					if state:
						ctx = Context(state, scan=self, rule=rule, match=m)
						if len(rule) > 2:
							ctx.aux = rule[2:]
						callout(ctx, *m.groups())
					return remains
			if DEBUG: DEBUG(" no match")


#
# A Scanner that passes input subject to byte count constraints.
#
class ByteLimit(object):

	def __init__(self, limit, threshold=None):
		self._limit = limit
		self._threshold = threshold
		self._delivered = 0

	def scan(self, buffer, callout):
		available = self._delivered + len(buffer)
		if self._threshold and available < self._threshold:
			return None		# not yet
		if available > self._limit:		# too much
			count = self._limit - self._delivered
			send = buffer[0:count]
			left = buffer[count:]
		else:
			count = len(buffer)
			send = buffer
			left = ''
		callout('limit-data', send, scan=self)
		self._delivered = self._delivered + count
		if self._delivered == self._limit:
			callout('limit-reached', scan=self)
		return left

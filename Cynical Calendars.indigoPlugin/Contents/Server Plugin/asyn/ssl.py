#
# asyn.ssl - SSL interface
#
# This uses the Python openssl module to implement
# an SSL pipe on top of an Raw Callable.
#
# This is based on the very old, very literal, essentially polling
# Python interface to SSL. Its only advantage is that it's actually
# available in Python 2.5. Python 2.6+ has much better interfaces,
# particularly when it comes to (ahem) actual certificate handling.
#
# Copyright 2013-2016 Perry The Cynic. All rights reserved.
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
from __future__ import with_statement
from contextlib import contextmanager

import OpenSSL.SSL
import OpenSSL.crypto

import asyn

DEBUG = None


#
# OpenSSL tends to use 16K buffering
#
BUFSIZE = 16 * 1024		# default read buffer size


#
# An asyn SSL adapter for OpenSSL.
#
class SSL(asyn.FilterCallable):
	""" An asyn adaptation of SSL.

		SSL presents the standard asyn Callable interface, forwarding data
		to the provided Selectable and imposing OpenSSL on the connection.
		This should work as a rough functional adapter to add SSL to any
		standard asyn.Stream-like data flow.
	"""
	def __init__(self, source=None, type=OpenSSL.SSL.TLSv1_METHOD, *args, **kwargs):
		asyn.FilterCallable.__init__(self)
		self.connection = None
		self.ctx = OpenSSL.SSL.Context(type)
		if source:
			self.open(source, *args, **kwargs)

	def open(self, source, accept=False, callout=None):
		super(SSL, self).open(source, callout=callout)
		self.connection = OpenSSL.SSL.Connection(self.ctx, None)	# no direct I/O object
		self._wbuf = ''
		if accept:
			self.connection.set_accept_state()
		else:
			self.connection.set_connect_state()
		self._startup = True
		self.handshake()		# start it off

	def close(self):
		super(SSL, self).close()
		self.connection = None

	def write(self, data):
		self._wbuf += data
		self._service()

	def handshake(self):
		with self.frame():
			self.connection.do_handshake()

	def shutdown(self):
		with self.frame():
			self.connection.shutdown()

	@contextmanager
	def frame(self):
		""" Perform an SSL operation and ignore non-error exceptions. """
		try:
			yield
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError, OpenSSL.SSL.WantX509LookupError):
			pass

	def _service(self):
		""" Make what progress we can by servicing the memory BIO and SSL. """
		while self.connection:	# (could be close()d in this loop)
			# send any buffered clear output to SSL
			if self._wbuf:
				with self.frame():
					written = self.connection.write(self._wbuf)
					if DEBUG: DEBUG("SSL ->", repr(self._wbuf[:written]))
					self._wbuf = self._wbuf[written:]
					continue
			# pull data from SSL and deliver it downstream
			with self.frame():
				try:
					rdata = self.connection.read(BUFSIZE)
					if DEBUG: DEBUG("SSL <-", repr(rdata))
					if self._startup:
						self.callout('start')
						self._startup = False
					self._scan(rdata)
					continue
				except OpenSSL.SSL.ZeroReturnError:		# EOF (it's a long story)
					self.callout('END')
					self.close()
					return
			# write side of memory BIO is managed by self._incoming
			# pull data from SSL's memory BIO and deliver it upstream
			if self.connection.want_read():
				with self.frame():
					wdata = self.connection.bio_read(BUFSIZE)
					if DEBUG: DEBUG("SSL -->", len(wdata))
					self.upstream.write(wdata)
					continue
			# no progress, done servicing
			return

	def incoming(self, ctx, data=None):
		""" Upstream tap. """
		if ctx.state == 'RAW':
			with self.frame():
				written = self.connection.bio_write(data)
				if DEBUG: DEBUG("SSL <--", written)
				assert written == len(data)		# memory BIOs have no size limit
				self._service()
		else:
			super(SSL, self).incoming(ctx, data)


#
# Regression test
#
if __name__ == "__main__":
	import sys
	import socket
	import getopt
	import asyn.selectable

	def cb(ctx, arg=None):
		if ctx.error:
			print '** ERROR **', ctx.error
			exit(0)
		elif ctx.state == 'END':
			print "End of data."
			exit(0)
		elif ctx.state == 'start':
			print "Negotiation complete."
		elif ctx.state == 'RAW':
			print "(%d bytes data)" % len(arg)
		else:
			print 'UNEXPECTED', ctx, arg

	control = asyn.Controller()
	res = socket.getaddrinfo('www.apple.com', 443, 0, socket.SOCK_STREAM)[0]
	s = socket.socket(*res[0:3])
	s.connect(res[4])
	stream = asyn.selectable.Stream(control, s)
	ssl = SSL(stream, callout=cb)

	control.schedule(lambda c: ssl.write("GET / HTTP/1.1\r\n"))
	control.schedule(lambda c: ssl.write("Host: www.apple.com\r\n"), after=2)
	control.schedule(lambda c: ssl.write("\r\n"), after=2.01)
#	control.schedule(lambda c: ssl.shutdown(), after=2.5)
	print "Running..."
	control.run()

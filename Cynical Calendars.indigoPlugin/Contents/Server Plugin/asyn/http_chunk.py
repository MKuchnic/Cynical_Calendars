#
# asyn.http_chunk - chunked coding FilterCallable
#
# Standard HTTP/1.1 chunked coder, read and write.
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
import zlib

import asyn


#
# Chunked-Transfer encoding (both sides)
#
class ChunkedCoder(asyn.FilterCallable):

	def __init__(self, source, callout=None):
		asyn.FilterCallable.__init__(self)
		if source:
			self.open(source, callout=callout)

	def open(self, source, callout=None):
		super(ChunkedCoder, self).open(source, callout=callout)
		self._pending = None
		self._remain = 0

	def incoming(self, ctx, data=None):
		if ctx.state == 'RAW':	# data
			self._pass_downstream(data)
		else:
			return super(ChunkedCoder, self).incoming(ctx, data)

	def _pass_downstream(self, data):
		if self._pending:
			data = self._pending + data
			self._pending = None
		while data:
			if self._remain:
				rlen = min(len(data), self._remain)	# remaining in pending chunk
				self._remain -= rlen
				sendlen = rlen - min(2-self._remain, 0) # don't send trailing \r\n
				self._scan(data[:sendlen])
				data = data[rlen:]
			assert self._remain == 0 or not data	# out of data or at chunk boundary
			if self._remain == 0 and data:			# start a new chunk
				hlen = data.find('\r\n')
				if hlen == -1:						# incomplete chunk header; defer
					self._pending = data
					return
				header = data[:hlen].partition(';')[0]	# discard any chunk extensions
				self._remain = int(header, 16) + 2	# count trailing \r\n
				data = data[hlen+2:]				# drop header \r\n
				if self._remain == 2:				# last-chunk
					self._pending = data
					# trailer processing is up to caller
					self.callout('END', data)
					return


	def write(self, data):
		""" Each chunk of data is sent as a separate chunk. """
		self.upstream.write("%X\r\n" % len(data))
		self.upstream.write(data + "\r\n")

	def write_flush(self):
		""" Finish an outbound stream. """
		# last-chunk marker + no trailers + \r\n
		self.upstream.write("0\r\n\r\n")
		super(ChunkedCoder, self).write_flush()

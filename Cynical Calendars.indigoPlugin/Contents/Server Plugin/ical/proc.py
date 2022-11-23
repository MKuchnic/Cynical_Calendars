#
# ical.proc - process live views of ical event space
#
# Copyright 2012-2016 Perry The Cynic. All rights reserved.
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
import time

import asyn
import asyn.dsmonitor
from Cocoa import NSRunLoop, NSDate

from ical.calendar import Calendar
from ical.event import Event, EventCore, Moment

DEBUG = None


#
# Notification events sent by the system
#
NOTIFY_INSERTED = 'CalInsertedRecordsKey'
NOTIFY_UPDATED = 'CalUpdatedRecordsKey'
NOTIFY_REMOVED = 'CalDeletedRecordsKey'


#
# Base class for live calendar processing.
#
class Processor(asyn.Callable):
	""" Process calendar state as it changes. """

	def __init__(self, control, calendars=None, callout=None, monitor=True):
		asyn.Callable.__init__(self, callout=callout)
		self.control = control
		self.calendars = calendars
		self._monitor_changes = monitor
		self._monitor = None
		self.raw_events = None
		self.events = None
		self.moments = None

	def close(self):
		if self._monitor:
			self._monitor.close()

	def load(self, reset=None):
		""" (Re)Load events from iCal and sort them into a time sequence.

		"""
		# collect raw_events
		raw = Event.events(calendars=self.calendars)
		self.raw_events = raw

		# collect events
		if not self.events or reset:
			uids = { }
			for ev in raw:
				if ev.uid not in uids:
					uids[ev.uid] = []
				uids[ev.uid].append(ev)
			self.events = dict([(uid, EventCore(evs)) for (uid, evs) in uids.items()])

		# collect all moments from all input events (including past starts)
		self.moments = reduce(lambda a,b: a+b, [ev.moments() for ev in raw], [])
		self.moments.sort(key=lambda m: m.when)

		# all done
		if DEBUG: DEBUG('Processor loaded', len(self.raw_events), 'events', len(self.moments), 'moments')
		self.callout('reload')
		self.monitor()

	def monitor(self):
		if self._monitor_changes and self._monitor is None:
			self._monitor = asyn.dsmonitor.DSMonitor(self.control,
				['com.apple.CalendarStore.CalDistributedEventsChangedNotification'],
				callout=self._core_event)
			if DEBUG: DEBUG("monitor loaded pid", self._monitor.pid)

	def _core_event(self, ctx, *it):
		if ctx.error:
			return self.callout(ctx)
		elif ctx.state == 'notify':
			self._notify_event(*it)
		elif ctx.state == 'END':
			self.callout('monitorfail')
			self.monitor()	# attempt relaunch
		else:
			print 'UNEXPECTED', ctx

	def _notify_event(self, name, info):
		assert info
		NSRunLoop.currentRunLoop().runUntilDate_(NSDate.date()) # update CalendarStore
		removed_uids = info.get(NOTIFY_REMOVED) or []
		inserted_uids = info.get(NOTIFY_INSERTED) or []
		changed_uids = info.get(NOTIFY_UPDATED) or []
		if DEBUG: DEBUG('Processor reschedule for db change', *info)
		self.pre_update((removed_uids, inserted_uids, changed_uids))
		(removed_evs, inserted_evs, changed_evs) = ([], [], [])
		for uid in removed_uids:
			if uid in self.events:
				removed_evs.append(self.events[uid])
				del self.events[uid]
		for uid in inserted_uids:
			inserted_evs.append(self._update(uid))
		for uid in changed_uids:
			changed_evs.append(self._update(uid))
		self.load()
		self.post_update((removed_evs, inserted_evs, changed_evs))

	# for override by child classes
	def pre_update(self, changes):
		pass
	def post_update(self, changes):
		pass

	#
	# Deal with incoming update notifications
	#
	def _update(self, uid):
		events = Event.for_uid(uid)
		if events:
			if uid in self.events:
				evc = self.events[uid].update(events)
			else:
				self.events[uid] = evc = EventCore(events)
			return evc

	def _purge(self, uid):
		if uid in self.events:
			del self.events[uid]

	def representative(self, uid):
		""" Return a representative event for a uid from the cache. Or none. """
		if uid in self.events:
			return self.events[uid].rep


#
# A Monitor calls out changes to events as they're reported by the calendar store
#
class Monitor(Processor):
	""" Monitor is a CalendarCore that calls out when events change.

	"""
	def __init__(self, control, calendars=None, callout=None, monitor=True):
		super(Monitor, self).__init__(control, calendars=calendars,
			callout=callout, monitor=monitor)
		self.sched = None

	def pre_update(self, changes):
		super(Monitor, self).pre_update(changes)

	def post_update(self, changes):
		super(Monitor, self).post_update(changes)
		self.callout('update', changes)


#
# A Performer calls out real-time events as they take place
#
class Performer(Processor):
	""" Performer is a CalendarCore that calls out when events begin and end.

	"""
	def __init__(self, control, calendars=None, callout=None, monitor=True):
		super(Performer, self).__init__(control, calendars=calendars,
			callout=callout, monitor=monitor)
		self.sched = None

	def load(self, reset=None):
		""" (Re)Load events from iCal and sort them into a time sequence. """
		super(Performer, self).load(reset=reset)

		# initialize self.current to the "now" position in moments, then start timers
		now = time.time()
		self.current = 0	# "now" position in self.moments
		while self.current < len(self.moments) and self.moments[self.current].when < now:
			self.current += 1
		self._schedule()

	def _schedule(self):
		if self.current < len(self.moments):
			moment = self.moments[self.current]
			if self.sched:
				if self.sched.when == moment.when:
					return
				self.sched.cancel()
			self.sched = self.control.schedule(self._timer_event, at=moment.when)
			self.sched.moment = moment
			if DEBUG: DEBUG('Performer scheduled in', moment.when - time.time(), moment)
			self.callout('schedule', moment)
		else:
			self.stop()
			self.callout('empty')

	def stop(self):
		if self.sched:
			if DEBUG: DEBUG('Performer schedule stop')
			self.sched.cancel()
			self.sched = None

	def _timer_event(self, ctx):
		if ctx.error:
			return self.callout(ctx)
		if ctx.state == 'TIMER':
			self._drain()
			self._schedule()
		else:
			print 'UNEXPECTED', ctx

	def pre_update(self, whatever):
		super(Performer, self).pre_update(whatever)
		self._drain()

	def post_update(self, whatever):
		super(Performer, self).post_update(whatever)
		self._schedule()

	def _drain(self):
		while self.current < len(self.moments) and self.moments[self.current].when <= time.time():
			moment = self.moments[self.current]
			self.current += 1
			self.callout('event', moment)


#
# A Computer does... well, nothing useful yet.
# Right now, it computes gaps between events and flags overlapping events.
#
class Computer(Processor):

	def __init__(self, control, calendars=None, callout=None, monitor=True):
		super(Computer, self).__init__(control, calendars=calendars,
			callout=callout, monitor=monitor)

	def analyze(self, overlaps=None, gaps=None, limit=None, all_day=False):
		active = set()
		overlap_sets = set()
		previous=None
		for m in self.moments:
			if m.type == Event.START:
				if gaps is not None and previous and not active:
					gaps.append((previous, m, m.event.start - previous.event.end))
				if all_day or not m.event.all_day:
					active.add(m.event)
				if len(active) > 1:
					if overlaps is not None:
						overlap = frozenset(active)
						if overlap not in overlap_sets:
							overlaps[m.when] = overlap
							overlap_sets.add(overlap)
			elif m.type == Event.END:
				if all_day or not m.event.all_day:
					active.remove(m.event)
				previous = m

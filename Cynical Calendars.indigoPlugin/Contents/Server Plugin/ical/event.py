#
# ical.event - iCal calendar events.
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
import types
import time
import datetime

import CalendarStore
from Cocoa import NSDistributedNotificationCenter, NSDate

from ical.calendar import Calendar, Error

_store = CalendarStore.CalCalendarStore.defaultCalendarStore()


# canonical timestamp formatter for str() & friends
def _dtstring(t):
	if t:
		return datetime.datetime.fromtimestamp(t).isoformat()

def _str(s):
	if s:
		return s.encode('ascii', 'replace')


#
# Calendaring Events as seen by your Macintosh
#
class Event(object):
	""" A calendaring Event.

		Event objects are not stable and are not cached. When they change, it is
		up to you to discard and refetch affected Events.
	"""
	def __init__(self, calev=None, **kwargs):
		if calev:
			self._load(calev)
		else:
			self._create(**kwargs)

	START = 'start'
	END = 'end'

	def moments(self):
		""" The Moments of an Event are its start end end time. """
		return [Moment(self, 'start'), Moment(self, 'end')]

	def save(self):
		""" Tell the calendaring system that we've changed an Event: "Make it so." """
		calev = self._event
		calev.setCalendar_(self.calendar._calendar)
		calev.setTitle_(self.title)
		calev.setNotes_(self.notes)
		calev.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(self.start))
		calev.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(self.end))
		calev.setLocation_(self.location)
		calev.setIsAllDay_(self.all_day)
		if self.occurrence:
			calev.setOccurrence_(NSDate.dateWithTimeIntervalSince1970_(self.occurrence))
		(ok, error) = _store.saveEvent_span_error_(self._event, CalendarStore.CalSpanAllEvents, None)
		if ok:
			self._load(self._event)
			return self
		else:
			raise Error(error)

	def remove(self):
		(ok, error) = _store.removeEvent_span_error_(self._event, CalendarStore.CalSpanAllEvents, None)
		if not ok:
			raise Error(error)

	def add_alarm(self, alarm):
		self._event.addAlarm_(alarm._make())

	@classmethod
	def events(cls, start=None, end=None, calendars=None, uid=None):
		""" Locate and return events satisfying given conditions. """
		start = NSDate.date() if start is None else NSDate.dateWithTimeIntervalSince1970_(start)
		end = NSDate.distantFuture() if end is None else NSDate.dateWithTimeIntervalSince1970_(end)
		if calendars is None:
			cals = _store.calendars()
		else:
			cals = [cal._calendar for cal in calendars]
		iclass = CalendarStore.CalCalendarStore
		if uid is None:
			predicate = iclass.eventPredicateWithStartDate_endDate_calendars_(start, end, cals)
		else:
			predicate = iclass.eventPredicateWithStartDate_endDate_UID_calendars_(start, end, uid, cals)
		return [Event(calev) for calev in _store.eventsWithPredicate_(predicate)]

	@classmethod
	def for_uid(self, uid, calendars=None):
		""" Fetch events for a given uid. This returns multiple objects only for repeating events. """
		return Event.events(uid=uid, calendars=calendars)

	def _load(self, calev):
		self._event = calev
		self.uid = calev.uid()
		self.title = calev.title()
		self.notes = calev.notes()
		self.occurrence = calev.occurrence().timeIntervalSince1970()
		self.start = calev.startDate().timeIntervalSince1970()
		self.end = calev.endDate().timeIntervalSince1970()
		self.detached = calev.isDetached()
		self.all_day = calev.isAllDay()
		self.location = calev.location()
		self.calendar = Calendar._make(calev.calendar())

	def _create(self, calendar, title, notes=None, start=None, duration=None, end=None, all_day=False, location=None, save=True):
		self._event = CalendarStore.CalEvent.event()
		self.calendar = calendar
		self.uid = None
		self.title = title
		self.notes = notes
		self.start = start or time.time()
		if end:
			self.end = end
		elif duration is not None:
			self.end = self.start + duration
		else:
			self.end = self.start + 60	# one minute
		self.all_day = all_day
		self.detached = False
		self.location = location
		self.occurrence = None
		if save:
			self.save()

	def __repr__(self):
		head = "<Event %s(%s) " % (_str(self.title), _str(self.notes))
		if self.all_day:
			head += "ALL_DAY "
		if self.detached:
			head += "DETACHED "
		tail = " loc=%s occ=%s uid=%s calendar=%s>" % (
			_str(self.location), _dtstring(self.occurrence), self.uid, _str(self.calendar.title))
		duration = self.end - self.start
		if duration >= 0 and duration < 86400:
			mid = "%s[%s]" % (_dtstring(self.start), duration)
		else:
			mid = "%s-%s" % (_dtstring(self.start), _dtstring(self.end))
		return head + mid + tail


#
# A mashed-up version of CalCalendarEvents
#
class EventCore(object):
	""" EventCore collects all repetitions of an event together in one object.

		CalendarStore offers stability by uid, but individual repeating events
		are identified by (uid, occurrence), where the occurrence is not stable.
		So we can't just stabilize Event (unless it's a non-repeating one).

		Instead, we consider "all repetitions of an event" to be an EventCore
		object. This includes any that were "detached" (individually edited).
	"""
	def __init__(self, calevs):
		self.update(calevs)

	def update(self, calevs):
		self.count = len(calevs)
		cores = [ev for ev in calevs if not ev.detached]
		assert cores
		self.events = calevs
		self.rep = cores[0]
		self.detached = [ev for ev in calevs if ev.detached]
		self.last_mod = time.time()
		return self

	@property
	def title(self):
		return self.rep.title

	@property
	def notes(self):
		return self.rep.notes

	@property
	def location(self):
		return self.rep.location

	@property
	def calendar(self):
		return self.rep.calendar

	@property
	def repeating(self):
		return self.count > 1

	def __repr__(self):
		if self.repeating:
			s = "<EventCore %s(%d+%d) mod=%s>" % (
				self.rep.title, len(self.events), len(self.detached),
				time.ctime(self.last_mod)
			)
		else:
			s = "<EventCore %s>" % self.rep
		return s.encode('ascii', 'replace')


#
# Moments are time points on objects.
# They are used to sort multi-timepoint objects such as Events into the time stream.
# The type of a Moment is the attribute name of the time value referenced; i.e.
# moment.when == getattr(moment, type) == moment.type
#
class Moment(object):
	""" A Moment is one time point of an Event or Task. """

	def __init__(self, event, type):
		self.event = event
		self.type = type
		self.when = getattr(event, type)

	@property
	def title(self):
		return self.event.title

	@property
	def notes(self):
		return self.event.notes

	@property
	def location(self):
		return self.event.location

	@property
	def calendar(self):
		return self.event.calendar

	def __str__(self):
		return "<Moment %s(%s) event=%s>" % (
			self.when, self.type, self.event
		)
	def __repr__(self): return str(self)

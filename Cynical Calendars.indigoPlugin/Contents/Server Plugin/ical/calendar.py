#
# ical.calendar - iCal Calendar Store calendars
#
# Calendars have stable UID values, so we can track them across changes using
# change notifications. Calendar objects are cached.
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
import CalendarStore

_store = CalendarStore.CalCalendarStore.defaultCalendarStore()


#
# Canonical error class
#
class Error(Exception):
	pass


#
# Calendars as seen by your Macintosh
#
class Calendar(object):
	""" A Calendar object.

		Calendar objects are stable and cached. If a Calendar changes, it will
		have its update() method called which updates its contents. Override this
		method to get change notifications, but be sure to call super().
	"""
	_cache = { }	# cache of calendars, by uid

	def __init__(self, calcal=None, **kwargs):
		""" Create a Calendar and cache it. """
		if calcal:
			self._load(calcal)
			self._cache[self.uid] = self
		else:
			self._create(**kwargs)

	def save(self):
		self._calendar.setTitle_(self.title)
		self._calendar.setNotes_(self.notes)
		#self._calendar.setColor_(?what?)
		(ok, error) = _store.saveCalendar_error_(self._calendar, None)
		if not ok:
			raise Error(error)

	def remove(self):
		(ok, error) = _store.removeCalendar_error_(self._calendar, None)
		if not ok:
			raise Error(error)

	def __str__(self):
		return '<Calendar %s(%s) type=%s uid=%s>' % (
			self.title, self.notes, self.type, self.uid)

	@classmethod
	def for_uid(cls, uid):
		""" Find a Calendar by UID. """
		if uid in cls._cache:
			return cls._cache[uid]
		calcal = _store.calendarWithUID_(uid)
		if calcal:
			return cls._make(calcal)
		return None

	@classmethod
	def for_title(cls, title):
		""" Find a Calendar by title. If there are multiple ones, pick one. """
		for calcal in _store.calendars():
			if calcal.title() == title:
				return cls._make(calcal)
		return None

	@classmethod
	def calendars(cls, type=None):
		""" Return all known calendars as a list. """
		return [cls._make(calcal) for calcal in _store.calendars()
			if type is None or type == calcal.type()]

	@classmethod
	def _make(cls, calcal):
		uid = calcal.uid()
		if uid in cls._cache:
			cal = cls._cache[uid]
			cal._load(calcal)
			return cal
		return Calendar(calcal)

	def _create(self, title="untitled", notes=None, color=None, save=True):
		self._calendar = CalendarStore.CalCalendar.calendar()
		self.title = title
		self.notes = notes
		self.color = color	# ignored
		if save:
			self.save()

	def _load(self, calcal):
		self._calendar = calcal
		self.uid = calcal.uid()
		self.title = calcal.title()
		self.notes = calcal.notes()
		self.type = calcal.type()
		self.editable = calcal.isEditable()
		#self.color = ?what?

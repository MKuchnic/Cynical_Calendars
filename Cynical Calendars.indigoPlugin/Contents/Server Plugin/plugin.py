#
# iCal calendaring plugin for Indigo 5
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
import re

import asyn
import ical

import cyin.filter
from cyin import iom, plug
from cyin import log, debug, error
from cyin.asynplugin import action
from cyin.check import *


#
# Map a calendar uid to a calendar object.
# Special-case 'ALL' to None (indicating all calendars).
#
def cal_uid(uid):
	if uid == 'ALL':
		return None
	else:
		return ical.Calendar.for_uid(uid)


#
# Events
#
class _EventCore(cyin.Event):

	title = cyin.PluginProperty(type=re.compile, required=False, reconfigure=False)
	notes = cyin.PluginProperty(type=re.compile, required=False, reconfigure=False)
	location = cyin.PluginProperty(type=re.compile, required=False, reconfigure=False)
	calendar = cyin.PluginProperty(type=cal_uid, required=False, reconfigure=False)

	def match(self, ev):
		""" Event match: all present components must match. """
		debug(self.name, "checking match for", ev.title)
		if self.calendar and self.calendar != ev.calendar:
			return False
		if self.title and not self.title.search(ev.title):
			return False
		if self.location and not self.location.search(ev.location):
			return False
		if self.notes and not self.notes.search(ev.notes):
			return False
		return True


class CalEvent(_EventCore):
	""" An Indigo event that fires when an iCal event begins or ends. """

	match_start = cyin.PluginProperty(type=bool, reconfigure=False)
	match_end = cyin.PluginProperty(type=bool, reconfigure=False)
	match_hourly = cyin.PluginProperty(type=bool, reconfigure=False)
	match_allday = cyin.PluginProperty(type=bool, reconfigure=False)
	execute_notes = cyin.PluginProperty(type=bool, reconfigure=False)

	def matches(self, moment):
		""" Event match: all present components must match. """
		if not self.match(moment):
			return False
		if moment.type == moment.event.START and not self.match_start:
			return False
		if moment.type == moment.event.END and not self.match_end:
			return False
		if moment.event.all_day and not self.match_allday:
			return False
		if not moment.event.all_day and not self.match_hourly:
			return False
		# it's a match
		notes = moment.event.notes
		title = moment.event.title
		indigo.variable.updateValue(1208226755, title)
		if notes and self.execute_notes:
			log("executing notes field for", self.name)
			cyin.eval.evaluate(notes, values={
				"self": self,
				"type": moment.type,
				"event": moment.event
			})
		return True

	class UI(cyin.ConfigUI):
		@cyin.checkbox
		def match_start_checked(self):
			if not self.match_start:
				self.match_end = True
		@cyin.checkbox
		def match_end_checked(self):
			if not self.match_end:
				self.match_start = True
		@cyin.checkbox
		def match_hourly_checked(self):
			if not self.match_hourly:
				self.match_allday = True
		@cyin.checkbox
		def match_allday_checked(self):
			if not self.match_allday:
				self.match_hourly = True


class CalChange(_EventCore):
	match_inserted = cyin.PluginProperty(type=bool)
	match_removed = cyin.PluginProperty(type=bool)
	match_changed = cyin.PluginProperty(type=bool)

	def matches(self, type, evcore):
		""" Event match: all present components must match. """
		if not self.match(evcore):
			return False

		if type == "inserted" and not self.match_inserted:
			return false
		if type == "removed" and not self.match_removed:
			return false
		if type == "changed" and not self.match_changed:
			return false

		# it's a match
		return True


#
# List all available calendars
#
class Calendars(cyin.filter.MenuFilter):

	def evaluate(self):
		return (
			[('ALL', 'All Calendars')] +
			sorted([(cal.uid, cal.title) for cal in ical.Calendar.calendars()], key=lambda s: s[1])
		)


#
# We don't want much from iCal - just change and timed events
#
class CalendarHandler(ical.Monitor, ical.Performer):
	pass


#
# The plugin itself.
#
class Plugin(cyin.asynplugin.Plugin):

	def startup(self):
		super(Plugin, self).startup()
		self.handler = CalendarHandler(control=self, callout=self._calev)
		self.handler.load()

	def _calev(self, ctx, data=None):
		""" Callout from the Calendar interface reporting something happened. """
		if ctx.error:
			return error(ctx.error)
		if ctx.state == 'event':
			debug("dispatching", data.type, "event", data.title)
			CalEvent.trigger(data)
		elif ctx.state == 'update':
			(removed, inserted, changed) = data
			for ev in removed:
				CalChange.trigger('removed', ev)
			for ev in inserted:
				CalChange.trigger('inserted', ev)
			for ev in changed:
				CalChange.trigger('changed', ev)
		elif ctx.state == 'reload':
			debug("calendar reloaded")
		elif ctx.state == 'empty':
			log("no future event(s) in calendars")

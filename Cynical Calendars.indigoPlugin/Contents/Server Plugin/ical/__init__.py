#
# ical - Mac OS/iOS calendar access.
#
# A Pythonic interface to calendars on Mac OS/iOS.
# This is not an ics parser; iCalendar does fine for that.
# It is an interface to the Mac's Calendar Store system,
# which manipulates actual calendar stores.
#
# Basic road map:
# ical.calendar.Calendar: A calendar object. Stable.
# ical.event.Event: A thin wrapper around ical events. Not stable.
# ical.event.EventCore: A digest of a cloud of events (if repeating). Stable in its way.
# ical.processor.CalendarProcessor: A "live" view of calendar space. Auto-updating.
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

#
# Collect selected parts of the base package
#
from ical.calendar import Calendar, Error
from ical.event import Event
from ical.proc import Processor, Monitor, Performer

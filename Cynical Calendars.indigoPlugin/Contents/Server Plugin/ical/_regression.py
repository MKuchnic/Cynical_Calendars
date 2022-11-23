#
# ical - Mac OS/iOS calendar access - regression test
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
import sys

import asyn
import ical
from ical.calendar import Calendar
from ical.event import Event, Moment


#
# Report and collect Calendar proc callbacks
#
samples = []

def cb(ctx, moment=None):
	if ctx.error:
		print 'ERROR', ctx
	elif ctx.state == 'event':
		delta = time.time() - base
		print "%s %s (%g)" % (moment.type, moment.event.title, delta)
		samples.append(delta)
		if moment.event.notes == 'THE END' and moment.type == 'end':
			control.close()
	elif ctx.state == 'reload':
		print "Events loaded (%d events, %d nodes, %d moments)" % (
			len(test.events), len(test.raw_events), len(test.moments))
	elif ctx.state == 'schedule':
		pass # print "Scheduled", moment
	elif ctx.state == 'empty':
		print "Calendar empty"
	else:
		print 'UNEXPECTED', ctx, moment


#
# Mix up the various calendar processors to show that they, well, mix well...
#
class Tester(ical.Performer):
	pass


#
# Set things up
#
print "ical/proc regression test (this will take about 20 seconds)"
calname = sys.argv[1] if len(sys.argv) > 1 else 'TESTING'
cal = Calendar.for_title(calname)
if cal:
	print "Using existing calendar %s for test" % cal.title
	temporary = False
else:
	cal = Calendar(title=calname, notes="Created for ical regression test")
	print "Using temporary calendar %s for test" % cal.title
	temporary = True

control = asyn.Controller()
test = Tester(control, calendars=[cal], callout=cb)

print "Creating test events"
base = int(time.time() + 2.5)	# time base (full second)
evs = []						# Events on record
expected = []					# expected callback time marks

#
# Schedule:            +0     +2    +3     +4    +5    +6    +7    +8
# <-----------------------A----------------------->
#                             <------------B------------>
#                             <------------------C------------------>
#                                   <---------!! -D- - - - - ->
#                                   ++     <-----E------>
# D is dynamically inserted at +3. E is dynamically removed at +4.5.
#
def make(title, start, end, notes=None, expect=[]):
	ev = ical.Event(calendar=cal, start=base+start, end=base+end, title=title, notes=notes)
	evs.append(ev)
	expected.extend(expect)
	return ev

def unmake(ev):
	ev.remove()
	evs.remove(ev)

make('Test A', start=-3600, end=5, expect=[5])
make('Test B', start=2, end=6, expect=[2, 6])
make('Test C', start=2, end=8, notes='THE END', expect=[2, 8])
event_d = make('Test D', start=3, end=7, expect=[3])	# will be removed around +4.5s
test.load()

# at +3s, insert 'Test E'
control.schedule(lambda ctx: make('Test E', start=4, end=6, expect=[4, 6]), at=base+3)

# at +4.5s, remove 'Test D'
control.schedule(lambda ctx: unmake(event_d), at=base+4.5)

#
# Run the event loop. The end of 'Test C' (Notes='THE END') will stop it.
#
print "Test starting..."
control.run()

#
# Clean up
#
if temporary:
	print "Removing temporary calendar %s" % cal.title
	cal.remove()
else:
	for ev in evs:
		ev.remove()

#
# Diagnose problems
#
expected.sort()
delta = [s - e for (s, e) in zip(samples, expected)]
min_delta = min(delta)
max_delta = max(delta)

if len(samples) != len(expected):
	print 'PROBLEM: Dropped events (needed %d got %d)' % (len(expected), len(samples))
	print 'EXPECTED:', expected
	print 'GOT:', samples
elif min_delta < 0:
	print 'PROBLEM: event(s) delivered too early (%g seconds slip)' % min_delta
elif max_delta > 0.1:
	print 'PROBLEM: event(s) delivered too late (%g seconds slip)' % max_delta
	print 'EXPECTED:', expected
	print 'GOT:', samples
else:
	print 'Test complete (worst slip is %g ms)' % (max_delta * 1000)

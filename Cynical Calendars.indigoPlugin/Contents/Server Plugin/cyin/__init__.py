#
# Cynical interface to Indigo 5
#
# The cyin package is an interface layer that makes writing
# Indigo 5+ plugins easier. It redefines the plugin environment
# quite substantially - instead of packing your one Plugin class
# with methods, you define separate classes for each device,
# event, and action of your plugin and then place methods into
# those.
#
# If you want to learn how to write conventional Indigo plugins,
# you should steer clear of cyin. It provides an environment that
# is substantially different from that provided by Indigo itself.
#
# Copyright 2011-2016 Perry The Cynic. All rights reserved.
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
DEBUG = "initial"		# the official plugin debug flag

from plug import Plugin							# the plugin itself
from iom import Device, Event, Action, DeviceAction # premier shadow classes
from core import log, error, debug				# noise makers
from core import variable						# helpers
from core import action, button, checkbox, menu	# decorators
from iom import device, trigger					# functions
from configui import ConfigUI					# classes
from filter import MenuFilter, MenuGenerator	# classes
from attr import PluginProperty, DeviceState, PluginPreference # descriptors
from attr import Variable, NamedVariable, cached, Cached
from confedit import FieldEditor				# classes

#
# The Plugin singleton itself.
# Automatically set when Indigo starts constructing it. None until then.
#
plugin = None

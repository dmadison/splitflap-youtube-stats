#
#  Project     Split-Flap YouTube Statistics
#  @author     David Madison
#  @link       github.com/dmadison/splitflap-youtube-stats
#  @license    MIT - Copyright (c) 2021 David Madison
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

__version__ = '1.0.0'

from time import sleep, monotonic
from datetime import datetime, timedelta
from humanize import naturaldelta

import re

from splitflap import Splitflap
import serial.tools.list_ports

import googleapiclient.discovery
import googleapiclient.errors

import argparse


def get_serial_port_list():
	"""
	Returns the list of serial ports, sorted by device name and
	excluding any which are missing descriptions
	"""
	ports = sorted(
		filter(
			lambda p: p.description != 'n/a',
			serial.tools.list_ports.comports(),
		),
		key=lambda p: p.device,
	)
	return ports


def get_serial_port(key=None, list_ports=False, verbose=False):
	"""
	Gets the device name for the given serial port. Takes a key value as an
	argument for either the name of the port or its position in the index
	(depending on type)

	Parameters:
		key (str): serial device or name, to check if the port is present
		key (int): index for the serial port in the list
		list_ports (bool): if no key is specified, print the available ports (if any)
		print_info (bool): print the debug output

	Returns:
		serial port device name as string, or 'None' if no port available
	"""

	ports = get_serial_port_list()
	out = None

	if isinstance(key, str):
		for port in ports:
			if port.device == key or port.name == key:
				out = port.device  # if provided key is in the list, return device name
				if verbose: print("Using specified serial port '{}'".format(out))
				break
		else:
			try:
				key = int(key)  # in case an int (index) is passed as str, we can try again
			except ValueError:
				if verbose: print("Specified serial port '{}' not found".format(key))

	if isinstance(key, int):
		if len(ports) >= key and key > 0:
			out = ports[key - 1].device  # if key is integer, return port index of key
			if verbose: print("Using indexed serial port '{}' ({}/{})".format(out, key, len(ports)))

	if out is None:
		if len(ports) > 0:
			if list_ports:
				print_serial_ports()
			out = ports[0].device  # by default, return first port in the list
			if verbose: print("Using default serial port '{}'".format(out))
		else:
			if verbose: print("No serial ports found on the system")

	return out


def print_serial_ports():
	"""
	Prints the available serial ports on the system (indexed at 1)
	"""

	print("Available serial ports:")
	ports = get_serial_port_list()
	for i, port in enumerate(ports):
		print('[{: 2}] {} - {}'.format(i+1, port.device, port.description))
	print()


class SplitflapPrinter(Splitflap):
	"""
	Extension of the Splitflap class for parsing and formatting
	data before sending it to the display

	Attributes:
		port_name (str): name of the serial port device
		serial (obj): the PySerial port object to which the display is connected
		last_line (str): the last line written to the display, filtered
	"""

	def __init__(self, port_name):
		self.port_name = port_name  # saving the port name for 'enter'
		self.serial = serial.Serial(port=None, baudrate=38400, timeout=1.0)  # not using the port name so this doesn't open immediately
		super().__init__(self.serial)
		self.last_line = ''  # buffer for display storage in demo mode

	def __enter__(self):
		self.open_serial()  # open the serial port
		return self

	def __exit__(self, type, value, traceback):
		self.close_serial()

	def open_serial(self):
		if self.port_name is None:
			print("Warning: No serial port specified, will *NOT* write to a display!")
			return

		# prevents board from restarting on USB connection (+ the subsequent re-home)
		# -- note that this has a conflict because the 'init' message is not re-echo'd
		# self.serial.rts = False
		# self.serial.dtr = False

		self.serial.port = self.port_name  # set the port name ('None' in the constructor)
		self.serial.open()
		super()._loop_for_status()  # and poll the device for status

	def close_serial(self):
		self.serial.close()

	def get_num_modules(self):
		"""
		If a display is connected returns the number of modules in the display.
		If a display is not connected, returns '8' for demo purposes

		Note that this overrides the base class' 'get_num_modules' method
		"""

		num_modules = super().get_num_modules()
		if (num_modules == 0) and (not self.serial.isOpen()):
			num_modules = 8  # demo size if no display attached (for padding previews)
		return num_modules

	def get_text(self):
		"""
		Returns the current text on the display. If the display is disconnected,
		returns the string we last tried to write to the display.

		Note that this overrides the base class' 'get_text' method
		"""

		if not self.serial.isOpen():
			return self.last_line
		return super().get_text()

	def filter_number(self, num):
		"""
		Filters a number for showing on the display. If the number is too
		large to fit on the display, it's truncated and  converted into
		scientific notation (E+N), returned as a string

		Parameters:
			num (int): number to filter

		Returns:
			number as a string in scientific notation, truncated to display size
		"""
		if num is None: return None
		try:
			int(num)
		except ValueError:
			return str(num)  # not a number, don't bother

		num_modules = self.get_num_modules()
		sci_prefix = "E+"
		places = len(str(num))  # number size in base 10

		# if the number is oversized and we have room to add some number and
		# a scientific prefix...
		if places > num_modules and num_modules - (len(sci_prefix) + 1) > 0:
			overage = places - num_modules + len(sci_prefix) + 1  # '+1' for the exponent (minimum)
			if len(str(overage)) > 1:
				overage = overage + len(str(overage)) - 1  # compensate for multi-digit exponents
			exp_str = sci_prefix + str(overage)  # "E+N"
			out = str(num)[0:num_modules - len(exp_str)] + exp_str  # trim to size and append string
			assert len(out) <= num_modules, "Error, scientific notation length error"
			return out
		return str(num)

	def parse_message_chunks(self, text, chunk_size=0, delimeter=' ,.-_'):
		"""
		Parses a text string into chunks based on the provided size,
		being mindful of word breaks

		Parameters:
			text (str): the text string to parse
			size (int): the size of each chunk
			delimeter (str): the character(s) used to signify word breaks

		Returns:
			list of text chunks
		"""

		# If text is smaller than chunk size, return full text
		text = str(text)
		text_size = len(text)
		if(chunk_size == 0 or text_size <= chunk_size):
			return [text]  # string as only element in list

		# process 1: split text by delimeters (separating words)
		words = re.split('[{}]+'.format(re.escape(delimeter)), text)

		# process 2: split words larger than the chunk size
		index = 0
		while index < len(words):
			word = words[index]
			if len(word) > chunk_size:
				sub_words = [word[i:i+chunk_size] for i in range(0, len(word), chunk_size)]
				del words[index]  # delete large version
				for sub in reversed(sub_words):
					words.insert(index, sub)  # re-add smaller pieces (in correct order)
			index += 1

		index = 0  # iterator
		finished = True  # completed output flag

		# process 3: see if we can combine some smaller words to fit into larger chunks
		while True:
			if (index >= len(words) - 1):
				if not finished:  # if we have to reprocess...
					index = 0  # reset iterator
					finished = True  # assume flag is good
				else:
					break

			new_word = words[index] + delimeter + words[index + 1]

			# if we have a new word that fits the chunk size, delete the
			# components, add the new word, and run the process again
			if len(new_word) <= chunk_size:
				del words[index + 1]
				del words[index]
				words.insert(index, new_word)
				finished = False

			index += 1

		return words

	def filter_string(self, string, replacement='?'):
		"""
		Filters a given string to the characters available in the
		split-flap display object.

		Parameters:
			string (str): the string to filter
			replacement (char): the replacement character if the parsed
				character is not present on the display

		Returns:
			filtered string
		"""
		str_list = list(string)  # use list instead of string so it's mutable

		for i, c in enumerate(str_list):
			new_char = replacement
			if self.in_character_list(c):
				continue  # in list, continue
			elif c.isalpha():
				alt_char = c.lower() if c.isupper() else c.upper()  # check for upper/lowercase equivalent
				if self.in_character_list(alt_char):
					new_char = alt_char

			str_list[i] = new_char  # replace character in list

		return ''.join(str_list)

	def align_text(self, text, align, length=None):
		"""
		Aligns a text string within a given length, by applying
		spaces as padding to the left and right

		Parameters:
			text (str): the text string to align
			align (str): the type of alignment, either 'left', 'right', or 'center'
			length (int): the length of the output string, the size of the display
			              by defualt

		Returns:
			string of aligned text
		"""
		if length is None:
			length = self.get_num_modules()  # use num modules by default

		if(align.lower() == 'left'):
			text = text.ljust(length)
		elif(align.lower() == 'right'):
			text = text.rjust(length)
		elif(align.lower() == 'center'):
			text = text.center(length)

		return text

	def set_text(self, text, align='left'):
		"""
		Sends a text string to the flaps, filtered to the available characters
		on the display and aligned left, right, or center

		Note that this overrides the base class' 'set_text' method

		Parameters:
			text (str): the text string to display
			align (str): alignment for the string, 'left', 'right', 'center', or None

		Returns:
			filtered string
		"""
		text = self.filter_string(text)  # filter characters to displayable ones
		text = self.align_text(text, align)  # align to size of display

		print("Setting flaps to: '{}'".format(text))

		# Don't rewrite text if it's already shown on the display
		# (avoids the delay from the microcontroller call/response)
		if self.get_text() != text and self.serial.isOpen():
			super().set_text(text)
		self.last_line = text  # save line for comparison if display disconnected

	def print(self, text='', align='left', dwell=2.0):
		"""
		Prints a text string to the display. If the text is too long to show,
		it will be split into chunks and shown piece by piece with a dwell
		time in-between.

		Parameters:
			text (str): the text string to print
			align (str): how to align the text on the display ('left', 'right', 'center')
			dwell (float): how long to wait before showing the next piece of text
		"""
		if type(text) == type(int) or type(text) == type(float):
			messages = [self.filter_number(text)]  # convert to scientific notation if needed
		else:
			chunk_size = self.get_num_modules()
			messages = self.parse_message_chunks(text, chunk_size)  # otherwise split up as text

		for message in messages:
			self.set_text(message, align)
			if dwell > 0.0:
				sleep(dwell)

	def clear(self, dwell=0.0):
		"""
		Clears the text on the display.

		Parameters:
			dwell (float): how long to wait after clearing the display. Default is no time.
		"""
		self.print('', dwell=dwell)

	def get_stat_prefix(self, prefixes, value=""):
		"""
		For a given set of text prefixes and a value to send to the display,
		returns the longest prefix that can be displayed alongside the value
		without exceeding the size of the display.

		If no prefix can fit on the display with the value, returns the longest
		value that can fit on the display by itself.

		Parameters:
			prefixes (str, list): list of string prefixes to prepend to the stat
			value: the statistic to display alongside the prefix

		Returns:
			prefix from list (str)
		"""
		if prefixes is None or prefixes == "": return None  # no string, nothing to do
		if type(prefixes) != list: prefixes = [prefixes]  # if not a list, make it a list so we can iterate
		prefixes.sort(reverse=True, key=len)

		value = str(value)  # for length comparisons

		# iterate through the prefixes to find which will fit on the display,
		# both without (single) and with the stat value (combined)
		longest_single = None
		longest_combined = None
		for p in prefixes:
			if longest_single == None and len(p) <= self.get_num_modules():
				longest_single = p  # longest prefix that fits on the display alone

			combined_str = p + ' ' + value
			if longest_combined == None and len(combined_str) <= self.get_num_modules():
				longest_combined = p  # longest prefix that fits on the display with the value

		if longest_combined is not None:
			return longest_combined  # ideally, get the combined version of prefix + stat
		elif longest_single is not None:
			return longest_single  # otherwise get the longest that fits on the display
		return prefixes[-1]  # if none fit, return smallest prefix in list

	def already_displaying_prefix(self, prefix):
		"""
		Checks if any in a list of prefixes are already being shown on the display

		Parameters:
			prefix (str, list): list of strings to check

		Returns:
			True if any prefix is present on the display, False otherwise
		"""
		if prefix is None: return False
		if not isinstance(prefix, list): prefix = [prefix]  # for iteration if not list already

		current = self.get_text() # current text on the display
		for p in prefix:
			p = self.filter_string(p)  # limit to text possible to show

			# note: could use regex to make this more robust (word boundaries)
			if current.count(p) > 0:
				return True  # present, no need to continue

		return False

	def print_stat(self, prefixes=None, value="", align='right', dwell=2.0, two_step=True):
		"""
		Prints a statistic with a text prefix beforehand. Ideally with a prefix
		shown at the same time as the statistic, otherwise displaying the prefix
		on a separate line beforehand.

		Parameters:
			prefixes (str, list): string or list of string prefixes to show beforehand
			value: the statistic to display after the prefix
			align (str): alignment of the value on the display. Defaults to 'right', which
			             places the prefix before the statistic value.
			dwell (float): how long to wait after displaying each line
			two_step (bool): always display the prefix before the statistic
		"""
		value = self.filter_number(value)  # convert to scientific notation if needed
		prefix = self.get_stat_prefix(prefixes, value)

		def invert_align(align):
			if align == 'left': ialign = 'right'
			elif align == 'right': ialign = 'left'
			else: ialign = align  # 'center' and others
			return ialign

		# if no prefix, print value as-is
		if prefix is None or prefix == "":
			self.print(value, align, dwell)

		# if both fit, create the string, print it, and call it a day
		elif len(prefix + ' ' + value) <= self.get_num_modules():
			# if we're doing a "two step", display the name and then the
			# value next to its name (for the visual effect)
			if two_step == True and not self.already_displaying_prefix(prefixes):
				self.print(prefix, align=invert_align(align), dwell=0.75)

			if align == 'left':
				combined_str = value + prefix.rjust(self.get_num_modules() - len(value))
			elif align == 'right':
				combined_str = prefix.ljust(self.get_num_modules() - len(value)) + value
			else:  # 'center' and others
				combined_str = value + ' ' + prefix
			self.print(combined_str, align=align, dwell=dwell)
	
		# otherwise if only one fits at a time, display the prefix
		# separately and then the value on its own line
		else:
			if two_step:
				self.print(prefix, align=invert_align(align), dwell=dwell)
			self.print(value, align=align, dwell=dwell)


def request_channel_info(yt, channel_id):
	request = yt.channels().list(
		part="snippet,contentDetails",
		id=channel_id
	)
	return request.execute()['items'][0]


def request_channel_stats(yt, channel_id):
	request = yt.channels().list(
		part="statistics",
		id=channel_id
	)
	return request.execute()['items'][0]


def request_latest_video(yt, playlist):
	request = yt.playlistItems().list(
		part='snippet,contentDetails',
		maxResults=1,
		playlistId=playlist
	)
	return request.execute()['items'][0]


def request_video_stats(yt, video_id):
	request = yt.videos().list(
		part='statistics',
		id=video_id
	)
	return request.execute()['items'][0]


class YouTubeStats(object):
	"""
	Main class tracking YouTube statistics for a given channel.

	Attributes:
		api (obj): YouTube API object, from the Google API client library
		channel_id (str): string for the YouTube channel ID being tracked
		channel_title (str): title of the YouTube channel, fetched at init
		uploads_playlist (str): ID string for the channel's uploads playlist
		_stat_objects (obj list): tracker objects for fetching/showing stats
	"""

	def __init__(self, api_key, channel_id):
		"""
		Parameters:
			api_key (str): YouTube API v3 key from Google
			channel_id (str): string for the YouTube channel ID being tracked
		"""
		self.api = googleapiclient.discovery.build('youtube', 'v3', developerKey=api_key)
		self.channel_id = channel_id

		try:
			response = request_channel_info(self.api, self.channel_id)
			self.channel_title = response['snippet']['title']
			self.uploads_playlist = response['contentDetails']['relatedPlaylists']['uploads']
		except KeyError:
			raise RuntimeError("Could not request channel info - check your channel ID")

		self._stat_objects = []  # empty list of stat objects for iteration

	def add_tracker(self, tracker):
		if tracker not in self._stat_objects:
			self._stat_objects.append(tracker)

	def remove_tracker(self, tracker):
		self._stat_objects.remove(tracker)

	def run_all(self):
		for stat in self._stat_objects:
			stat.run()

	def get_sleep_time(self):
		"""
		Gets the amount of time, in seconds, until the next update according
		to the tracker object update rates
		"""
		soonest = None
		for obj in self._stat_objects:
			next_update = obj.last_update + obj.update_rate
			if soonest is None or soonest > next_update:
				soonest = next_update
		
		if soonest is None:
			return 0  # no sleep delay
		return max(soonest - monotonic(), 0)  # next update according to the monotonic timer

class YouTubeStatTracker(object):
	"""
	Base class for tracking YouTube statistics and showing them on the display.

	Derived classes need to define two functions:
		fetch(): for getting new info from the API, returns True if successful
		show(): for displaying that info on the split-flap display

	Attributes:
		youtube (obj): YouTubeStats object, for channel + API info
		display (obj): SplitflapPrinter object, for display output
		update_rate (int): number of seconds between data / show updates
		last_update (int): timestamp of the previous update, using monotonic timer
	"""

	def __init__(self, youtube, display, update_rate=600):
		self.youtube = youtube
		self.display = display

		self.update_rate = update_rate
		self.last_update = None

		self.youtube.add_tracker(self)

	def __del__(self):
		self.youtube.remove_tracker(self)

	def run(self):
		# check rate limiter
		now = monotonic()  # using a monotonic clock so updates are evenly spaced regardless of the system clock setting
		if not (self.last_update is None or (now >= self.last_update + self.update_rate)):
			return  # not time to update yet
		self.last_update = now

		# and using datetime for the debug output, so the user can keep track with an actual clock
		#next_update = (datetime.now() + timedelta(seconds=self.update_rate)).strftime("%Y-%m-%d %H:%M:%S")
		current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		next_update = naturaldelta(timedelta(seconds=self.update_rate))  # or using human-readable update time
		print("--- {} Fetching update for '{}', next update in {} ---".format(current_time_str, self.__class__.__name__, next_update))

		if(self.fetch() == True):
			self.show()


class SubscriberCounter(YouTubeStatTracker):
	"""
	YouTubeStatTracker for showing the number of subscribers for a channel

	Attributes:
		subs (int): number of subscribers for the channel
		diff (int): difference in subscribers from the previous update
		sub_prefixes (str, list): string prefixes to display before the
		                          sub count, if requested
		show_diff (bool): whether to show the difference in subs
	"""

	def __init__(self, show_prefix=True, show_diff=True, *args, **kwargs):
		"""
		Parameters:
			show_prefix (bool): whether to show the "subscriber" prefix 
			                    before the sub count
			show_diff (bool): whether to show the increase in the sub count
			                  before the sub count itself
		"""
		super().__init__(*args, **kwargs)
		self.subs = None
		self.diff = 0
		if show_prefix:
			self.sub_prefixes = [
				"Subscribers",
				"Subs",
				"Sub",
			]
		else: self.sub_prefixes = None
		self.show_diff = show_diff

	def fetch(self):
		try:
			response = request_channel_stats(self.youtube.api, self.youtube.channel_id)
			new_subs = int(response['statistics']['subscriberCount'])
			old_subs = self.subs if self.subs else new_subs  # avoiding first call 'None'

			self.subs = new_subs
			self.diff = new_subs - old_subs
			return True
		except KeyError:
			print("Error: Could not retrieve subscriber count")
			return False

	def show(self):
		if self.subs is None:
			print("Error: No sub count available to show")
			return

		flash_prefix = True  # show 'subs' on its own before value
		if self.diff > 0 and self.show_diff:
			self.display.print_stat(self.sub_prefixes, "+{}".format(self.diff))
			flash_prefix = False  # do not flash the prefix if we already showed it here

		self.display.print_stat(self.sub_prefixes, self.subs, two_step=flash_prefix)

class ChannelStats(YouTubeStatTracker):
	"""
	YouTubeStatTracker for showing the channel statistics, including the
	title of the channel, view count, and video count

	Attributes:
		view_count (int): total number of views on the channel
		video_count (int): total number of videos on the channel
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.view_count = None
		self.video_count = None

	def fetch(self):
		try:
			response = request_channel_stats(self.youtube.api, self.youtube.channel_id)
			self.view_count = int(response['statistics']['viewCount'])
			self.video_count = int(response['statistics']['videoCount'])
			return True
		except KeyError:
			print("Error: Could not retrieve channel stats")
			return False

	def show(self):
		if self.view_count is None or self.video_count is None:
			print("Error: No channel stats to display")
			return

		self.display.print("Channel")
		self.display.print(self.youtube.channel_title)
		self.display.print_stat("Views", self.view_count)
		self.display.print_stat("Vids", self.video_count)


class RecentVideoStats(YouTubeStatTracker):
	"""
	YouTubeStatTracker for showing the recent video statistics, including the
	number of views, number of likes, and number of comments

	Attributes:
		update_rate_videos (int): update rate, in seconds, to check for new videos
		update_rate_stats (int): update rate, in seconds, to display statistics on the latest video
		recent_days (int): number of days to consider 'recent' for a video
		recent_hours (int): number of hours to consider 'recent' for a video
		latest_timestamp (str): timestamp of the latest video, ISO8601
		video_title (str): title of the latest video
		latest_video (str): video ID of the latest video, as str
		displayed_video (str): video ID of the currently displayed video, as str
	"""
	def __init__(self, update_rate_videos, update_rate_stats, days_recent=3, hours_recent=0, *args, **kwargs):
		self.update_rate_videos = update_rate_videos  # update rate to check for new videos
		self.update_rate_stats = update_rate_stats  # update rate to check for video stats on the most recent vid

		super().__init__(update_rate=self.update_rate_videos, *args, **kwargs)

		self.recent_days = days_recent  # number of days to consider 'recent' for a video
		self.recent_hours = hours_recent  # ibid for hours

		self.latest_timestamp = None  # latest timestamp of the video, as a string
		self.video_title = None
		self.latest_video = None
		self.displayed_video = None

	def fetch(self):
		try:
			response = request_latest_video(self.youtube.api, self.youtube.uploads_playlist)
			self.latest_timestamp = response['contentDetails']['videoPublishedAt']
			self.latest_video = response['contentDetails']['videoId']
			self.video_title = response['snippet']['title']
		except KeyError:
			print("Error: Could not retrieve latest video info")
			return False

		new_video = False
		try:
			video_time = datetime.strptime(self.latest_timestamp, '%Y-%m-%dT%H:%M:%SZ')
			cutoff_time = datetime.now() - timedelta(days=self.recent_days, hours=self.recent_hours)

			if video_time > cutoff_time: new_video = True
		except ValueError:
			pass # not a valid string format

		if new_video:
			self.update_rate = self.update_rate_stats  # update at the rate we want to show stats
		else:
			self.update_rate = self.update_rate_videos  # no success, keep checking at 'new' video poll rate
			video_time_str = datetime.strftime(video_time, "%Y-%m-%d %H:%M:%S")
			cutoff_time_str = datetime.strftime(cutoff_time, "%Y-%m-%d %H:%M:%S")
			print("Latest video, '{}', was not \"recent\" (published {}, cutoff time is {})".format(self.video_title, video_time_str, cutoff_time_str))

		return new_video

	def show(self):
		self.display.print("New Vid!")

		# have we shown this video on the display before? if not, save the ID
		# and display the video's title
		if self.latest_video != self.displayed_video:
			self.displayed_video = self.latest_video
			self.display.print(self.video_title)
		self.display.clear()

		video_stats = request_video_stats(self.youtube.api, self.latest_video)

		# Each dictionary key is the statistic key for the JSON dictionary,
		# and each dictionary value is the string to display before the key
		stat_dict = {
			'viewCount' : 'Views',
			'likeCount' : 'Likes',
			'commentCount' : 'Comments'
		}

		for key in stat_dict:
			try:
				stat = video_stats['statistics'][key]
				self.display.print_stat(stat_dict[key], stat)
			except KeyError:
				print("Error: Could not retrieve '{}' value from video stats".format(key))




def splitflap_youtube_stats(api_key, channel_id, port, show_intro=False):
	# bundles the API object along with the associated channel info (fetched on initialization)
	stats = YouTubeStats(api_key, channel_id)

	print("Fetching statistics for YouTube channel '{}' ({})".format(stats.channel_title, stats.channel_id))
	print("Please wait: connecting to split-flap display controller...\n")

	with SplitflapPrinter(port) as flaps:
		if show_intro:
			flaps.print("YouTube Stats", align='center')
			flaps.print("v" + __version__, align='right')
			flaps.clear(dwell=2.0)  # wait briefly before starting

		# check for channel statistics every hour, including the channel name, total views,
		# and number of videos (subscribers are handled separately)
		ChannelStats(youtube=stats, display=flaps, update_rate=3600)

		# check for new videos every 5 minutes, if there is a new and recent video 
		# then check for and display stats every 30 minutes
		RecentVideoStats(youtube=stats, display=flaps, update_rate_videos=300, update_rate_stats=1800, days_recent=3)

		# check for new subscribers every 2 minutes, showing the difference in subs as well
		SubscriberCounter(youtube=stats, display=flaps, show_diff=True, update_rate=120)

		while True:
			stats.run_all()  # fetch and push all stat trackers
			sleep_time = stats.get_sleep_time()
			if sleep_time > 0:
				print("\t(sleeping for {})".format(naturaldelta(timedelta(seconds=sleep_time))))
				sleep(sleep_time)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(prog="Split-Flap YouTube Statistics")

	parser.add_argument("api_key", help="your Google API key", type=str)
	parser.add_argument("channel_id", help="the YouTube channel ID to get statistics for", type=str)

	parser.add_argument("--port", "-p", help="name or index of the serial port to use")
	parser.add_argument("--demo", help="run without a connected display", action='store_true', default=False)
	parser.add_argument("--intro", help="show info strings at script startup", action='store_true', default=False)

	parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)

	args = parser.parse_args()

	title_str = parser.prog + ' v' + __version__
	print("\n\n" + title_str)
	print('-' * len(title_str) + '\n')

	port = None
	if not args.demo:  # don't fetch a port if we're operating without a display
		if args.port:
			try:
				port = int(args.port)  # if integer, use that (for index in the list)
			except ValueError:
				port = args.port  # otherwise use the string version of the port name
		port = get_serial_port(port, list_ports=True, verbose=True)

	splitflap_youtube_stats(args.api_key, args.channel_id, port, args.intro)

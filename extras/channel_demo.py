#
#  Project     Split-Flap YouTube Statistics
#  @author     David Madison
#  @link       github.com/dmadison/splitflap-youtube-stats
#  @license    MIT - Copyright (c) 2021 David Madison
#
#  File: channel_demo.py
#  Desc: loads channel info from file and displays channel name and subscriber
#        count on the split-flap display
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

import os
import sys
from time import sleep

from youtube_info_local import retrieve_youtube_info  # for retrieving channel info

# path hackery to import the main script as a module without moving it
current_directory = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.abspath(os.path.join(current_directory, os.pardir))
script_directory = os.path.join(parent_dir, 'src')
sys.path.insert(1, script_directory)

from splitflap_youtube_stats import SplitflapPrinter, get_serial_port, print_serial_ports


def read_channels(directory='youtube_info'):
	print("Reading channels...")
	channels = retrieve_youtube_info(directory, verbose=False)  # get channels from local
	channels = sorted(channels, key=lambda v: v['snippet']['title'])  # sort channels by channel name
	print("Successfully read {} channels from disk\n".format(len(channels)))
	assert len(channels) > 0, "Error: Must have at least 1 channel to use"
	return channels


def select_serial_port():
	print_serial_ports()
	port_selection = input("Select a serial port: ")
	port = get_serial_port(port_selection, list_ports=False, verbose=True)
	print()
	return port


def select_channel(channels):
	last_channel = len(channels)
	channel_names = [channel['snippet']['title'] for channel in channels]

	print("Channel Selection Options:")
	for i, name in enumerate(channel_names):
		print('[{: 2}] {}'.format(i+1, name))
	print()
	while True:
		selection = input("Select a channel (1-{}): ".format(last_channel))
		try:
			selection = int(selection)
			if selection <= 0 or selection > last_channel:
				raise ValueError
		except ValueError:
			print("Not a valid selection, please try again\n")
			continue

		break  # valid selection

	return channels[selection-1]  # compensating for 1-index


def show_channel(flaps, channel):
	channel_name = channel['snippet']['title']
	print("\nDisplaying channel '{}'".format(channel_name))

	sleep(3)  # prevent input keystroke audio from showing up
	flaps.print(channel_name, dwell=2.00)
	flaps.print(dwell=0.75)
	flaps.print_stat(["Subscribers","Subs","Sub"], channel['statistics']['subscriberCount'], dwell=1.25)
	sleep(2)
	flaps.print()
	print()


def main():
	title = "Split-Flap Channel Demo"
	print('\n' * 2 + title)
	print('-' * len(title) + '\n')

	channels = read_channels()

	with SplitflapPrinter(select_serial_port()) as flaps:
		while True:
			channel = select_channel(channels)
			show_channel(flaps, channel)



if __name__ == "__main__":
	main()

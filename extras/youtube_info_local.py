#
#  Project     Split-Flap YouTube Statistics
#  @author     David Madison
#  @link       github.com/dmadison/splitflap-youtube-stats
#  @license    MIT - Copyright (c) 2021 David Madison
#
#  File: youtube_info_local.py
#  Desc: fetches and saves YouTube channel info to file for later retrieval
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

import googleapiclient.discovery
import googleapiclient.errors

from datetime import datetime
import os
import json


class Channel:
	def __init__(self, name, id=None, username=None):
		self.name = name
		if id:
			self.id = id
			self.username = None
		elif username:
			self.id = None
			self.username = username

	def get_identifier(self):
		if self.id:
			return { 'id' : self.id }
		elif self.username:
			return { 'forUsername' : self.username }
		raise RuntimeError("No channel identifier present")


def save_youtube_info(api_key, resource, request_function, directory=None, verbose=True):
	"""
	Fetches YouTube API information for a data resource, then saves that data
	to a local file for later retrieval

	Parameters:
		api_key (str): YouTube Data API developer key, from Google
		resource (list/str): identifier of data resource, either as string or list of strings
		request_function (func): the function to request data from the API, taking the API object
		                         and resource ID as parameters
		directory (str): output directory for the saved data files
	"""

	if type(resource) != list:
		resource = [resource]  # make identifiers iterable if they're not already

	if directory is None:  # if no directory specified...
		directory = os.path.dirname(os.path.realpath(__file__))  # save in same folder as script
	else:
		try:
			os.mkdir(directory)
		except FileExistsError:
			pass
		directory = os.path.abspath(directory)

	api = googleapiclient.discovery.build('youtube', 'v3', developerKey=api_key)
	now = datetime.now().strftime("%Y-%m-%d")  # save time as str for filenames
	function_name = str(request_function.__name__).replace("request_", "")  # get rid of 'request' prefix

	for r in resource:
		info = request_function(api, r)  # get info from API (dictionary)
		json_info = json.dumps(info, indent = 4)  # convert to standardized json

		id = info['id']  # extract resource ID from response for write

		output_path = os.path.join(directory, '{}_{}_{}.txt'.format(now, id, function_name))  # output text file path

		if verbose: print("Saving {} for {} to file {}".format(function_name, id, output_path))
		with open(output_path, 'wb') as file:
			file.write(str(json_info).encode('utf-8'))


def request_channel_info(api, channel):
	if isinstance(channel, Channel):
		keyword_arg = channel.get_identifier()
	else:
		keyword_arg = { 'id' : channel }  # assuming ID and not username

	request = api.channels().list(
		part="snippet,contentDetails,statistics",
		**keyword_arg
	)
	return request.execute()['items'][0]

def save_channel_info(*args, **kwargs):
	save_youtube_info(*args, **kwargs, request_function=request_channel_info)


def request_video_info(api, video_id):
	request = api.videos().list(
		part="snippet,contentDetails,statistics",
		id=video_id
	)
	return request.execute()['items'][0]

def save_video_info(*args, **kwargs):
	save_youtube_info(*args, **kwargs, request_function=request_video_info)


def retrieve_youtube_info(directory=None, verbose=True):
	"""
	Retrieves YouTube API information saved as text in a local directory

	Parameters:
		directory (str): input directory containing JSON text files

	Returns:
		YouTube data dictionaries, as a list
	"""

	if directory is None:  # read from same folder as script, ignoring script itself
		script_directory = os.path.dirname(os.path.realpath(__file__))
		script_file = os.path.basename(__file__)
		file_list = [f for f in os.listdir(script_directory) if (os.path.isfile(os.path.join(script_directory, f)) and f != script_file)]
	else:
		file_directory = os.path.abspath(directory)
		file_list = [os.path.join(file_directory, f) for f in os.listdir(file_directory) if os.path.isfile(os.path.join(file_directory, f))]

	data = []
	for name in file_list:
		with open(name, 'rb') as file:
			try:
				info = json.loads(file.read().decode('utf-8'))
				data.append(info)
				if verbose: print("Successfully read YouTube data from {}".format(name))
			except json.decoder.JSONDecodeError or KeyError:
				if verbose: print("Error: Could not read YouTube data from {}".format(name))

	return data


def get_youtube_info_local(yt, id):
	"""
	Drop-in replacement for API 'get' functions in splitflap_youtube_stats.py

	Arguments:
		yt (obj): YouTube API object, unused
		id (str): resource ID string
	"""
	info = retrieve_youtube_info('youtube_info', verbose=False)
	info = list(filter(lambda x:x['id'] == id, info))[0]  # filter to my channel
	return info


if __name__ == "__main__":
	api_key = 'super-secret-api-key'

	folder_name = 'youtube_info'  # folder to read and save from
	video_folder = os.path.join(folder_name, 'video')  # folder for video info (nested)

	channels = [
		Channel('Dave Madison', id='UCoMRklnEz2Lk21_AkwAGkog'),
		Channel('Colin Furze', username='colinfurze'),
		Channel('Simone Giertz', id='UC3KEoMzNz8eYnwBC34RaKCQ'),
		Channel('Zack Freedman', username='ZackFreedman'),
		Channel('Becky Stern', id='UCsI_41SZafKtB5qE46WjlQQ'),
		Channel('Brian Lough', username='witnessmenow'),
		Channel('Scott Bezek', username='scottbez1'),
	]

	save_channel_info(api_key, channels, directory=folder_name)
	save_video_info(api_key, '4hwadqDmcfY', directory=video_folder)
	print()

	data  = retrieve_youtube_info(folder_name)
	data += retrieve_youtube_info(video_folder)
	print("\nSuccessfully read {} info files into list".format(len(data)))

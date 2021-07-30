# Split-Flap YouTube Statistics

This project fetches channel statistics from YouTube's Data API and sends them to a [DIY split-flap display](https://www.partsnotincluded.com/building-diy-split-flap-displays/).

For more information, [check out the project article here](https://www.partsnotincluded.com/split-flap-youtube-subscriber-counter).

## Getting Started

Running the script requires [Python 3](https://www.python.org/downloads/). The script was developed using Python 3.8 - note that earlier versions may not be compatible.

To use the script, first install the package dependencies using pip:

```shell
python -m pip install -r requirements.txt
```

The script can be executed from the command line. There are two required positional arguments:
* `api_key` - the Google API key for accessing the YouTube Data API. If you do not have an API key, you can create one [here](https://console.developers.google.com/).
* `channel_id` - the ID of the YouTube channel to fetch statistics for. For most people this can be found as part of the URL of the channel. If you do not know your channel ID, Google has some information on finding it [here](https://support.google.com/youtube/answer/3250431).

You must also have a [split-flap display](https://github.com/scottbez1/splitflap) connected via serial. You can specify the port using the `--port` argument, otherwise the script will use the default port. If you do not have a display you can test the output using the `--demo` command line flag. Note that some features may not work correctly without a connected display.

## License

The `splitflap` script for communicating with the display is a copy from the [splitflap](https://github.com/scottbez1/splitflap) project, and is licensed under the [Apache v2 license](https://github.com/scottbez1/splitflap/blob/master/LICENSE.txt).

All other files, including the `splitflap_youtube_stats` script, are licensed under the terms of the [MIT license](https://opensource.org/licenses/MIT). See the [LICENSE](LICENSE) file for more information.

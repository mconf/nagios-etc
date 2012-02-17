#!/usr/bin/python

import sys
import bigbluebutton_info
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description = "Fetches information from a BigBlueButton server")
    parser.add_argument("--host",
        required = True,
        help = "the BigBlueButton HOST",
        dest = "host",
        metavar = "<IP or URI>")
    parser.add_argument("--port",
        type = int,
        choices = xrange(0, 65535),
        default = 80,
        help = "the PORT used to connect to the API",
        dest = "port",
        metavar = "<0 - 65535>")
    parser.add_argument("--salt",
        help = "the SALT of your BigBlueButton server",
        dest = "salt",
        metavar = "<salt>")
    return parser.parse_args()


# TODO: receive thresholds and return a status code when they're exceeded
# TODO: set a different status when the connection to the server fails
# TODO: set a different status when the response has a failure code
def main():
    """
    Fetches the following information from a BigBlueButton server:
    - Number of meetings
    - Number of users connected (in all meetings)
    - Number of users with video (in all meetings)
    - Number of users with audio (in all meetings)
    Returns the codes:
    0:  all got well

    """

    args = parse_args()

    result = bigbluebutton_info.fetch(args.host, args.port, args.salt)

    status =  "Meetings: " + str(result.meetingCount)
    status += ", Users: " + str(result.userCount)
    status += ", User with video: " + str(result.videoCount)
    status += ", User with audio: " + str(result.audioCount)
    status += " |" + str(result.meetingCount) + ";"
    status += str(result.userCount) + ";"
    status += str(result.videoCount) + ";"
    status += str(result.audioCount) + ";"

    sys.stdout.write(status)
    sys.exit((0))

if __name__ == '__main__':
    main()

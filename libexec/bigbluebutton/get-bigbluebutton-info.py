#!/usr/bin/python

import sys
import bigbluebutton_info
import argparse

# Parse the limits given by the user into an array
def info_limits(string):
    limits = [ [0,0,0,0], [0,0,0,0] ] # defaults
    user_limits = string.split(";")
    if len(user_limits) != 2:
        msg = "%r is not a valid limit range" % string
        raise argparse.ArgumentTypeError(msg)

    for i, val in enumerate(user_limits):
        values = val.split(",")
        if len(values) != 4:
            msg = "%r is not a valid limit range" % val
            raise argparse.ArgumentTypeError(msg)
        limits[i] = values

    return limits

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
        required = True,
        help = "the SALT of your BigBlueButton server",
        dest = "salt",
        metavar = "<salt>")
    parser.add_argument("--limits",
        type = info_limits,
        default = "0,0,0,0;0,0,0,0",
        help = "the LIMITS for the service to enter CRITICAL and WARNING status. Format: \"meetings,users,audios,videos;meetings,users,audios,videos\", the first set for the CRITICAL status and the second for the WARNING",
        dest = "limits",
        metavar = "<limits>")
    return parser.parse_args()

# Check the service status using the limits informed by the user and the results from BBB
# Ex: get_status([2,3,2,1], [[0,0,30,30],[0,25,10,10]])
def get_status(result, limits):
    for status, limit_set in enumerate(limits):
        for i, limit in enumerate(limit_set):
            limit = int(limit)
            # 0 means disabled
            if limit > 0:
                # if the result is over the limit
                if result[i] >= limit:
                    # 1:WARNING, 2:CRITICAL
                    return 2-status
    # all OK
    return 0

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
    0: all ok
    1: entered the WARNING status
    2: entered the CRITICAL status
    1: couldn't get an anwser from BBB, is at the UNKNOWN status
    """

    # args
    args = parse_args()

    # get the data from BBB
    result = bigbluebutton_info.fetch(args.host, args.port, args.salt)

    # output
    msg =  "Meetings: " + str(result.meetingCount)
    msg += ", Users: " + str(result.userCount)
    msg += ", User with audio: " + str(result.audioCount)
    msg += ", User with video: " + str(result.videoCount)
    msg += " |" + str(result.meetingCount) + ";"
    msg += str(result.userCount) + ";"
    msg += str(result.audioCount) + ";"
    msg += str(result.videoCount) + ";"
    sys.stdout.write(msg)
    status = get_status([result.meetingCount, result.userCount, result.audioCount, result.videoCount], args.limits)
    sys.exit((status))

if __name__ == '__main__':
    main()

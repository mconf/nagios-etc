#!/usr/bin/python

import sys
import bigbluebutton_info

def print_usage():
    print "Usage:"
    print "   info <IP>:<PORT> <SALT>"
    exit(0)

if len(sys.argv) == 1:
    print_usage()

if sys.argv[1] == "info":
    if len(sys.argv) != 4:
        print_usage()
    result = bigbluebutton_info.info(sys.argv[2], sys.argv[3])

    print "Meetings: " + str(result.meetingCount)
    print "Users: " + str(result.userCount)
    print "Users with video: " + str(result.videoCount)
    print "Users with audio: " + str(result.audioCount)

else:
    print_usage();


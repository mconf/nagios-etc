import sys, re
import bbb_api

# To store the parsed arguments
class InfoArgs:
    url = ""
    salt = ""

# To store the information fetched from a BBB server
class BigBlueButtonInfo:
    meetingCount = 0
    userCount = 0
    videoCount = 0
    audioCount = 0

    def addToUsers(self, count):
        self.userCount += count
    def addToAudioUsers(self, count):
        self.audioCount += count
    def addVideoUser(self):
        self.videoCount += 1

def info_args(url, salt):
    args = InfoArgs()
    args.salt = salt
    args.url = url

    if not re.match("http[s]?://", args.url, re.IGNORECASE):
        args.url = "http://" + args.url
    if not args.url[len(args.url)-1] == '/':
        args.url += "/"
    args.url += "bigbluebutton/"

    return args

# Fetch information from a BBB server
def info(url, salt):
    args = info_args(url, salt)
    result = BigBlueButtonInfo()

    meetings = bbb_api.getMeetings(args.url, args.salt)
    result.meetingCount = len(meetings["meetings"])

    for name, meeting in meetings["meetings"].iteritems():
        meeting_info = bbb_api.getMeetingInfo(meeting["meetingID"], meeting["moderatorPW"], args.url, args.salt)
        result.addToUsers(int(meeting_info["participantCount"]))
        result.addToAudioUsers(int(meeting_info["listenerCount"]))

        for uid, user in meeting_info["attendees"].iteritems():
            if re.match("true", user["hasVideoStream"], re.IGNORECASE):
                result.addVideoUser()

    return result

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
    def addMeeting(self):
        self.meetingCount += 1
    def addToUsers(self, count):
        self.userCount += count
    def addToAudioUsers(self, count):
        self.audioCount += count
    def addVideoUser(self):
        self.videoCount += 1
    def limits(self):
        return [self.meetingCount, self.userCount, self.audioCount, self.videoCount]

# Creates a InfoArgs object with the complete BBB url and salt
def info_args(host, port, salt):
    args = InfoArgs()
    args.salt = salt
    args.url = host
    if port != None:
        args.url += ":" + str(port)

    if not re.match("http[s]?://", args.url, re.IGNORECASE):
        args.url = "http://" + args.url
    if not args.url[len(args.url)-1] == '/':
        args.url += "/"
    args.url += "bigbluebutton/"

    return args

# Returns true if the meeting_info object has support to the new tags
# <listenerCount> and <hasVideoStream>
def has_audio_video_support(info):
    return "listenerCount" in info

# Fetch information from a BBB server
def fetch(host, port, salt):
    args = info_args(host, port, salt)
    result = BigBlueButtonInfo()

    meetings = bbb_api.getMeetings(args.url, args.salt)

    # just in case there are no meetings in the server
    if "meetings" in meetings and meetings["meetings"] != None:
        for name, meeting in meetings["meetings"].iteritems():

            # only if the meeting is running
            if re.match("true", meeting["running"], re.IGNORECASE):
                result.addMeeting()
                meeting_info = bbb_api.getMeetingInfo(meeting["meetingID"], meeting["moderatorPW"], args.url, args.salt)
                result.addToUsers(int(meeting_info["participantCount"]))

                # the server has the new tags in the api response
                if has_audio_video_support(meeting_info):
                    result.addToAudioUsers(int(meeting_info["listenerCount"]))

                    for uid, user in meeting_info["attendees"].iteritems():
                        if re.match("true", user["hasVideoStream"], re.IGNORECASE):
                            result.addVideoUser()

                # no support to the new api
                else:
                    result.audioCount = -1
                    result.videoCount = -1

    return result

import sys
import os
if os.name != 'posix':
    sys.exit('platform not supported')
import curses
import atexit
import time
import commands
import re
import string

import psutil

# --- curses stuff
def tear_down():
    win.keypad(0)
    curses.nocbreak()
    curses.echo()
    curses.endwin()

win = curses.initscr()
atexit.register(tear_down)
curses.endwin()
lineno = 0

def bytes2human(n):
    """
    >>> bytes2human(10000)
    '9.8 K'
    >>> bytes2human(100001221)
    '95.4 M'
    """
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i+1)*10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.2f %s' % (value, s)
    return '%.2f B' % (n)

def trunc(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    slen = len('%.*f' % (n, f))
    return str(f)[:slen]

def dataFormater(dataList, formats):
	'''receives a data list and a format list returning the medium value until de Nth position of each format item'''
	returnList = []
	for form in formats:
		i = 0
		total = 0.0
		while i < form:
			if  i >= len(dataList): #prevent illegal mem access
				return returnList
			if isinstance(dataList[i], int):
				total += float(dataList[i])
			if isinstance(dataList[i], float):
				total += dataList[i]
			else:
				total += float(re.sub(r'[a-zA-Z]', '', dataList[i]))
			i += 1
		returnList.append(trunc(total/form, 2))
	return returnList

def sendReport(destination, service, state, message):
	'''send report to nagios server'''
	
	#mount data 
	send_nsca_dir = "/usr/local/nagios/bin"
	send_nsca_cfg_dir = "/usr/local/nagios/etc"

	command = (
		"/usr/bin/printf \"%s\t%s\t%s\t%s\n\" \"localhost\" \"" 
		+ service + "\" \"" 
		+ state + "\" \"" 
		+ message + "\" | " 
		+ send_nsca_dir + "/send_nsca -H " 
		+ destination + " -c " 
		+ send_nsca_cfg_dir + "/send_nsca.cfg" 
		)

	commandoutput = commands.getoutput(command)
	print commandoutput
	

class CircularList:
	#TOFIX: the circular list is not a temporal circular, it is a memory allocation circular.
	def __init__(self, size):
		self.size = size
		self.position = 0
		self.dataList = []
		
	def __len__(self):
		return self.size
		
	def Append(self, data):
		self.position = self.position + 1
		if(self.position >= self.size):
			self.position = 0
		self.dataList.insert(self.position, data)
		
	def GetList(self):
		return self.dataList

def processorReporter(refreshRate, sendRate):
	'''thread function to collect and report processor data'''
	
	cpuDataList = CircularList(60)
	sendTime = sendRate
	
	#convert to thread while
	
	while sendTime >= 0:
		sendTime = sendTime - 1
		cpu_quantity = 0
		cpu_percent = 0
		cpu_quantity = cpu_quantity + 1
		cpuDataList.Append(psutil.cpu_percent(interval=0.1, percpu=False))
	
	formatedData = dataFormater(cpuDataList.GetList(), [3,9])
	
	destination = "143.54.12.174"
	service = "Processor Performance Report"
	state= "3"
	host = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`"
	message = host + " Processor usage " + str(formatedData)
	sendReport(destination, service, state, message)

def networkReporter(refreshRate, sendRate):
	'''thread function to collect and report network data'''
	sentDataList = CircularList(60)
	receivedDataList = CircularList(60)
	
	#TODO: convert to thread while
	sendTime = sendRate
	
	while sendTime >= 0:
		sendTime = sendTime - 1
		
		#collect data
		tot_before = psutil.network_io_counters()
		pnic_before = psutil.network_io_counters(pernic=True)
		#win.refresh()
		time.sleep(refreshRate)
		tot_after = psutil.network_io_counters()
		pnic_after = psutil.network_io_counters(pernic=True)
		
		#format bytes to string
		name = pnic_after.keys()[1] #get one network interface only
		stats_before = pnic_before[name]
		stats_after = pnic_after[name]
		
		bytesSent = bytes2human(stats_after.bytes_sent - stats_before.bytes_sent)
		bytesReceived = bytes2human(stats_after.bytes_recv - stats_before.bytes_recv)
		
		#store on a circular list
		sentDataList.Append(bytesSent)
		receivedDataList.Append(bytesReceived)
		
		
	formatedSentData = dataFormater(sentDataList.GetList(), [3,9])
	formatedReceivedData = dataFormater(receivedDataList.GetList(), [3,9])
	
	destination = "143.54.12.174"
	service = "Network Performance Report"
	state= "3"
	host = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`"
	message = host + " Received data " + str(formatedReceivedData) + " Sent data " + str(formatedSentData)
	
	sendReport(destination, service, state, message)
	
def refresh_window():
	'''main loop to call all the reporters'''
	
	print "Main Loop called"
	#here we should have the main call to the reporter threads
	networkReporter(0.1, 20)
	processorReporter(0.1, 20)
	
	win.refresh()
	
def main():
    try:
		'''
		if len(sys.argv) != 3:
			print "usage: -refreshRate -sendRate"
		else:
			refreshRate = sys.argv[1]
			sendRate = sys.argv[2]
			while 1:
				refresh_window()
		'''
		while True:
			refresh_window()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()

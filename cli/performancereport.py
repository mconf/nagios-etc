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
from threading import Thread

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

def toKbps(n):
    return float(n >> 7)
    
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
	win.refresh()

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

class processorReporter(Thread):
	def __init__ (self,refreshRate, sendRate, destination, formatList, timeLapseSize):
		Thread.__init__(self)
		self.refreshRate = refreshRate
		self.sendRate = sendRate
		self.destination = destination
		self.formatList = formatList
		self.timeLapseSize = timeLapseSize
		self.warn = "50.000"
		self.crit = "90.000"
		self.mini = "0"
      
	def run(self):
		'''thread function to collect and report processor data'''
		cpuDataList = CircularList(self.timeLapseSize)
		while True:
			sendTime = self.sendRate
			while sendTime >= 0:
				sendTime = sendTime - 1
				cpu_quantity = 0
				cpu_percent = 0
				cpu_quantity = cpu_quantity + 1
				cpuDataList.Append(psutil.cpu_percent(interval=0.1, percpu=False))

			formatedData = dataFormater(cpuDataList.GetList(), self.formatList)
			
			service = "Processor Performance Report"
			state= "3"
			host = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`"
			#example:
			#printf "%s\t%s\t%s\t%s\n" "192.168.0.100" "CPU Load" "0" "Status information|cpu1=50%;90;95;0;100" | ~/downloads/nsca-2.7.2/src/send_nsca -H 192.168.0.100 -c ~/downloads/nsca-2.7.2/sample-config/send_nsca.cfg
			message = "cpu load:" + str(formatedData)
			message += "|"
			for Format, Data in zip(self.formatList, formatedData) :
				message += "load" + str(Format) + "=" + str(Data) + "%;" + self.warn + ";" + self.crit + ";"  + self.mini + "; "
				#example:
				#load1=0.040;5.000;10.000;0; load5=0.010;4.000;6.000;0; load15=0.000;3.000;4.000;0;
			sendReport(self.destination, service, state, message)

class networkReporter(Thread):
	def __init__ (self, refreshRate, sendRate, destination, formatList, timeLapseSize):
		Thread.__init__(self)
		self.refreshRate = refreshRate
		self.sendRate = sendRate
		self.destination = destination
		self.formatList = formatList
		self.timeLapseSize = timeLapseSize
		self.warn = "400.000"
		self.crit = "900.000"
		self.mini = "0"
      
	def run(self):
		'''thread function to collect and report network data'''
		sentDataList = CircularList(self.timeLapseSize)
		receivedDataList = CircularList(self.timeLapseSize)
		while True:
			sendTime = self.sendRate
			
			while sendTime >= 0:
				sendTime = sendTime - 1
				
				#collect data
				tot_before = psutil.network_io_counters()
				pnic_before = psutil.network_io_counters(pernic=True)
				time.sleep(self.refreshRate)
				tot_after = psutil.network_io_counters()
				pnic_after = psutil.network_io_counters(pernic=True)
				
				#format bytes to string
				name = pnic_after.keys()[1] #get one network interface only
				stats_before = pnic_before[name]
				stats_after = pnic_after[name]
				
				bytesSent = toKbps(stats_after.bytes_sent - stats_before.bytes_sent)
				bytesReceived = toKbps(stats_after.bytes_recv - stats_before.bytes_recv)
				
				#store on a circular list
				sentDataList.Append(bytesSent)
				receivedDataList.Append(bytesReceived)
			
			formatedSentData = dataFormater(sentDataList.GetList(), self.formatList)
			formatedReceivedData = dataFormater(receivedDataList.GetList(), self.formatList)
			
			service = "Network Performance Report"
			state= "3"
			host = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`"
			message = host + " Received data " + str(formatedReceivedData) + " Sent data " + str(formatedSentData)
			
			message = "sent traffic:" + str(formatedSentData) + " received traffic:" + str(formatedReceivedData)
			message += "|"
			for Format, SentData, ReceivedData in zip(self.formatList, formatedSentData, formatedReceivedData) :
				message += "recv" + str(Format) + "=" + str(ReceivedData) + "kbps;" + self.warn + ";" + self.crit + ";"  + self.mini + "; "
				message += "sent" + str(Format) + "=" + str(SentData) + "kbps;" + self.warn + ";" + self.crit + ";"  + self.mini + "; "
				#example:
				#load1=0.040;5.000;10.000;0; load5=0.010;4.000;6.000;0; load15=0.000;3.000;4.000;0;
			sendReport(self.destination, service, state, message)
	
def refresh_window():
	'''main loop to call all the reporters'''
	
	print "Main Loop called"
	destination = "143.54.12.174"
	threadsList = []
	refreshRate = 0.1
	sendRate = 20
	formatList = [3,15,60]
	timeLapseSize = 60
	
	
	#here we should have the main call to the reporter threads
	
	#networkReporter thread
	current = networkReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	
	#processorReporter thread
	current = processorReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	
	for reporterThread in threadsList:
		reporterThread.start()

	input("sair")
	
	for reporterThread in threadsList:
		reporterThread._Thread__stop()
	
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
		refresh_window()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()

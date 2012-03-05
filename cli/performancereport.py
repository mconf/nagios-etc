import sys
import os
if os.name != 'posix':
    sys.exit('platform not supported')
import atexit
import time
import commands
import re
import string
import argparse
from threading import Thread

import psutil

# Exit statuses recognized by Nagios
NAGIOS_OK = "0"
NAGIOS_WARNING = "1"
NAGIOS_CRITICAL = "2"
NAGIOS_UNKNOWN = "3"

# Globals

HOSTNAME = "localhost"
DEBUGMODE = False
	


def toKbps(n):
    return float(n >> 7)
    
def trunc(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    slen = len('%.*f' % (n, f))
    return str(f)[:slen]

def gcd(a, b):
	'''greatest commom divisor for two integers'''
	while b != 0:
		a, b = b, a%b
	return abs(a)

def recgcd(numberList):
	'''recursive call of greatest commom divisor for a list of integers'''
	last = numberList[0]
	for number in numberList:
		last = gcd(last, number)
	return last

def messageFormater(dataList, formatList, name, formatMultiplier, unit, warn, crit, mini):
	'''format a message given the data, name and parameters desired'''
	message = ""
	for Format, Data in zip(formatList, dataList) :
		message += name + str(Format * formatMultiplier) + "=" + str(Data) + unit + ";" + str(warn) + ";" + str(crit) + ";"  + str(mini) + "; "
	return message
	#example:
	#load1=0.040;5.000;10.000;0; load5=0.010;4.000;6.000;0; load15=0.000;3.000;4.000;0;
	
def dataFormater(dataList, formats):
	'''receives a data list and a format list returning the medium value until de Nth position of the data list for each format item'''
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
	
def checkStatus(levelList, crit, warn):
	returnState = NAGIOS_OK
	for strLevel in levelList:
		level = float(strLevel)
		if level > crit:
			return NAGIOS_CRITICAL
		if level > warn:
			returnState = NAGIOS_WARNING
	return returnState

class CircularList:
	#TOFIX?: the circular list is not a temporal circular, it is a memory allocation circular.
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

class processesAnalyzer(Thread):
	'''collect cpu process data and print them to the stdout'''
	def __init__ (self,refreshRate):
		Thread.__init__(self)
		self.refreshRate = refreshRate
		self.terminate = False
	
	def kill(self):
		self.terminate = True
		
	def run(self):
		while True:
			if self.terminate:
				return
			processList = []
			for p in psutil.process_iter():
				processList.append(p)
			try:
				processesSortByMem = sorted(processList, key=lambda p: p.get_memory_percent(), reverse=True)
				processesSortByProc = sorted(processList, key=lambda p: p.get_cpu_percent(interval=0), reverse=True)
				#to use later. Print top 5 processes on mem and proc usage
				printProcStatus = False
				if printProcStatus:
					print "sorted by memory usage"
					for i, p in zip(range(5),processesSortByMem):
						print (" process name: " + str(p.name) + " mem use: " + str(p.get_memory_percent()))
					print "\n"
					print "sorted by processor usage"
					for i, p in zip(range(5),processesSortByProc):
						print (" process name: " + str(p.name) + " proc use: " + str(p.get_cpu_percent(interval=0)))
					print "\n\n\n\n\n\n\n\n"
			except psutil.NoSuchProcess:
				#just to catch the error and avoid killing the thread
				#the raised error is because the process maybe killed before the get_cpu_percent or get_memory_percent calls
				pass
			time.sleep(self.refreshRate)

class Reporter(Thread):
	'''base reporter thread class'''
	def __init__ (self, refreshRate, sendRate, destination, formatList, timeLapseSize):
		Thread.__init__(self)
		self.terminate = False
		self.refreshRate = refreshRate
		self.sendRate = sendRate
		self.destination = destination
		self.formatList = formatList
		self.timeLapseSize = timeLapseSize
		self.warn = 70
		self.crit = 90
		self.mini = 0
		self.state = NAGIOS_UNKNOWN
		self.service = "Unknown Service"
	
	def kill(self):
		#send kill sign to terminate the thread in the next data collection loop
		self.terminate = True
		
	def threadLoop(self):
		#nothing on the base class 
		#Should be implemented by each reporter service and set the self.state and self.message variables
		return

	def sendReport(self):
		'''send report to nagios server'''
		#mount data 
		send_nsca_dir = "/usr/local/nagios/bin"
		send_nsca_cfg_dir = "/usr/local/nagios/etc"
		command = (
			"/usr/bin/printf \"%s\t%s\t%s\t%s\n\" \"" + HOSTNAME + "\" \"" 
			# `ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`
			+ self.service + "\" \"" 
			+ self.state + "\" \"" 
			+ self.message + "\" | " 
			+ send_nsca_dir + "/send_nsca -H " 
			+ self.destination + " -c " 
			+ send_nsca_cfg_dir + "/send_nsca.cfg" 
			)
		commandoutput = commands.getoutput(command)
		if DEBUGMODE:
			print "---------------------------------"
			print self.service, self.state, self.message
			print command
			
	def run(self):
		while True:
			if self.terminate:
				return
			#call method that actually do what the threads needs to do
			self.threadLoop()
			
			#test for empty parameters before sending the data
			if not (self.service == None or self.destination == None or self.state == None or self.message == None):
				self.sendReport()
			elif DEBUGMODE:
				print "-> send data ERROR: " + self.service + self.state + self.message

class memoryReporter(Reporter):
	'''reporter class to collect and report memory data'''
	def __init__(self, refreshRate, sendRate, destination, formatList, timeLapseSize):
		Reporter.__init__(self, refreshRate, sendRate, destination, formatList, timeLapseSize)
		self.service = "Memory Report"
		self.memDataList = CircularList(self.timeLapseSize)
		
	def threadLoop(self):
		sendTime = self.sendRate
		while sendTime >= 0:
			sendTime -= 1
			time.sleep(self.refreshRate)
			memUse = psutil.phymem_usage().percent
			self.memDataList.Append(memUse)
		formatedData = dataFormater(self.memDataList.GetList(), self.formatList)
		#message mount
		self.message = ("mem usage:" + str(formatedData) + "|" 	
						+ messageFormater(formatedData, self.formatList, "muse", self.refreshRate, "%", self.warn, self.crit, self.mini))
		#state mount
		self.state = checkStatus(formatedData, self.crit, self.warn)

class processorReporter(Reporter):
	'''reporter class to collect and report processor data'''
	def __init__ (self,refreshRate, sendRate, destination, formatList, timeLapseSize):
		Reporter.__init__(self, refreshRate, sendRate, destination, formatList, timeLapseSize)
		self.service = "Processor Report"
		self.cpuDataList = CircularList(self.timeLapseSize)
		
	def threadLoop(self):
		sendTime = self.sendRate
		while sendTime >= 0:
			sendTime -= 1
			self.cpuDataList.Append(psutil.cpu_percent(self.refreshRate, percpu=False))
		formatedData = dataFormater(self.cpuDataList.GetList(), self.formatList)
		#message mount
		self.message = ("cpu load:" + str(formatedData) + "|" + 
			messageFormater(formatedData, self.formatList, "proc", self.refreshRate, "%", self.warn, self.crit, self.mini))
		#state mount
		self.state = checkStatus(formatedData, self.crit, self.warn)

class networkReporter(Reporter):
	'''reporter class to collect and report network data'''
	def __init__ (self, refreshRate, sendRate, destination, formatList, timeLapseSize, interface):
		Reporter.__init__(self, refreshRate, sendRate, destination, formatList, timeLapseSize)
		self.service = "Network Report"
		self.interface = interface
		self.sentDataList = CircularList(self.timeLapseSize)
		self.receivedDataList = CircularList(self.timeLapseSize)
		
	def threadLoop(self):
		sendTime = self.sendRate
		while sendTime >= 0:
			sendTime -= 1
			#collect data
			tot_before = psutil.network_io_counters()
			pnic_before = psutil.network_io_counters(pernic=True)
			time.sleep(self.refreshRate)
			tot_after = psutil.network_io_counters()
			pnic_after = psutil.network_io_counters(pernic=True)
			#format bytes to string
			stats_before = pnic_before[self.interface]
			stats_after = pnic_after[self.interface]
			bytesSent = toKbps(stats_after.bytes_sent - stats_before.bytes_sent)
			bytesReceived = toKbps(stats_after.bytes_recv - stats_before.bytes_recv)
			#store on a circular list
			self.sentDataList.Append(bytesSent)
			self.receivedDataList.Append(bytesReceived)
		formatedSentData = dataFormater(self.sentDataList.GetList(), self.formatList)
		formatedReceivedData = dataFormater(self.receivedDataList.GetList(), self.formatList)
		#message mount
		self.message = ("sent traffic: " + str(formatedSentData) + " received traffic: " + str(formatedReceivedData) + " |" +
			messageFormater(formatedReceivedData, self.formatList, "recv", self.refreshRate, "kbps", self.warn, self.crit, self.mini) +
			messageFormater(formatedSentData, self.formatList, "sent", self.refreshRate, "kbps", self.warn, self.crit, self.mini))
		#state mount
		sentState = int(checkStatus(formatedSentData, self.crit, self.warn))
		recvState = int(checkStatus(formatedReceivedData, self.crit, self.warn))
		if sentState > recvState:
			self.state = str(sentState)
		else:
			self.state = str(recvState)

def parse_args():
	parser = argparse.ArgumentParser(description = "Fetches information for a Performance Reporter")
	parser.add_argument("--interface",
		required = False,
		help = "network interface to be monitored",
		dest = "interface",
		default = "eth0",
		metavar = "<INTERFACE>")
	parser.add_argument("--hostname",
		required = False,
		help = "name of the caller host",
		dest = "hostname",
		default = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`",
		metavar = "<HOST>")
	parser.add_argument("--format",
		required = False,
		help = "format list that the data should be send. Example: \"3,15,60\" ",
		dest = "data_format",
		default = "3,15,60",
		metavar = "<data_format>")
	parser.add_argument("--sendrate",
		required = False,
		help = "set how many refresh ticks should happen before each data send",
		dest = "sendrate",
		default = "20",
		metavar = "<sendrate>")
	parser.add_argument("--server",
		required = False,
		help = "ip adress of the nagios server",
		dest = "server",
		default = "143.54.12.174",
		metavar = "<server>")
	parser.add_argument("--debug",
		required = False,
		help = "debug mode: print output",
		dest = "debug",
		action='store_true')
	return parser.parse_args()

def main_loop(args):
	'''main loop to call all the reporters'''
	global DEBUGMODE
	global HOSTNAME
	threadsList = []
	
	#args set
	DEBUGMODE = args.debug
	interface = args.interface
	HOSTNAME = args.hostname
	destination = args.server
	sendRate = int(args.sendrate)
	formatList = eval(args.data_format)
	#calculate new refresh rate with de greatest commom divisor
	refreshRate = recgcd(formatList)
	#set circular list size according to maximum data resolution
	timeLapseSize = (max(formatList)/refreshRate)
	#ajust each time interval according to the new time resolution
	formatList = [x/refreshRate for x in formatList]

	#here we should have the main call to the reporter threads
	#networkReporter thread
	current = networkReporter(refreshRate, sendRate, destination, formatList, timeLapseSize, interface)
	threadsList.append(current)
	#processorReporter thread
	current = processorReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	#memoryReporter thread
	current = memoryReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	#processesAnalyzer thread
	current = processesAnalyzer(refreshRate)
	#threadsList.append(current)

	#start every thread
	for reporterThread in threadsList:
		reporterThread.start()

	raw_input("Press Enter to kill all threads...\n")

	#send kill sign to all threads
	for reporterThread in threadsList:
		reporterThread.kill()
	#wait for each thread to finish
	for reporterThread in threadsList:
		reporterThread.join()
	
def main():
    try:
		# args
		args = parse_args()
		main_loop(args)
    except (KeyboardInterrupt, SystemExit):
        pass
if __name__ == '__main__':
    main()

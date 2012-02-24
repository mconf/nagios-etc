import sys
import os
if os.name != 'posix':
    sys.exit('platform not supported')
import atexit
import time
import commands
import re
import string
from threading import Thread

import psutil

def toKbps(n):
    return float(n >> 7)
    
def trunc(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
    slen = len('%.*f' % (n, f))
    return str(f)[:slen]

def messageFormater(dataList, formatList, name, unit, warn, crit, mini):
	'''format a message given the data, name and parameters desired'''
	message = ""
	for Format, Data in zip(formatList, dataList) :
				message += name + str(Format) + "=" + str(Data) + unit + ";" + str(warn) + ";" + str(crit) + ";"  + str(mini) + "; "
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
	returnState = "0"
	for strLevel in levelList:
		level = float(strLevel)
		if level > crit:
			return "2"
		if level > warn:
			returnState = "1"
	return returnState

def sendReport(destination, service, state, message):
	'''send report to nagios server'''
	
	#mount data 
	send_nsca_dir = "/usr/local/nagios/bin"
	send_nsca_cfg_dir = "/usr/local/nagios/etc"

	command = (
		"/usr/bin/printf \"%s\t%s\t%s\t%s\n\" \"`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`\" \"" 
		# `ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`
		+ service + "\" \"" 
		+ state + "\" \"" 
		+ message + "\" | " 
		+ send_nsca_dir + "/send_nsca -H " 
		+ destination + " -c " 
		+ send_nsca_cfg_dir + "/send_nsca.cfg" 
		)

	commandoutput = commands.getoutput(command)
	#print message

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
			
			processesSortByMem = sorted(processList, key=lambda p: p.get_memory_percent(), reverse=True)
			processesSortByProc = sorted(processList, key=lambda p: p.get_cpu_percent(interval=0), reverse=True)
			
			printProcStatus = False
			if printProcStatus:
				print "sorted by memory usage"
				for i, p in zip(range(0,5),processesSortByMem):
					print (" process name: " + str(p.name) + 
							" mem use: " + str(p.get_memory_percent()))
				print "\n"
				print "sorted by processor usage"
				for i, p in zip(range(0,5),processesSortByProc):
					print (" process name: " + str(p.name) + 
							" proc use: " + str(p.get_cpu_percent(interval=0)))
				print "\n\n\n\n\n\n\n\n"
			time.sleep(self.refreshRate)

class memoryReporter(Thread):
	'''thread class to collect and report memory data'''
	def __init__ (self,refreshRate, sendRate, destination, formatList, timeLapseSize):
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
		self.service = "Memory Report"
		
	def kill(self):
		self.terminate = True
		
	def run(self):
		memDataList = CircularList(self.timeLapseSize)
		
		while True:
			
			if self.terminate:
				return
			
			sendTime = self.sendRate	
			while sendTime >= 0:
				sendTime -= 1
				time.sleep(self.refreshRate)
				memUse = psutil.phymem_usage().percent
				memDataList.Append(memUse)
			
			formatedData = dataFormater(memDataList.GetList(), self.formatList)
			message = "mem usage:" + str(formatedData)
			message += "|"
			message += messageFormater(formatedData, self.formatList, "muse", "%", self.warn, self.crit, self.mini)
			
			state = checkStatus(formatedData, self.crit, self.warn)
			
			sendReport(self.destination, self.service, state, message)
			
class processorReporter(Thread):
	'''thread class to collect and report processor data'''
	def __init__ (self,refreshRate, sendRate, destination, formatList, timeLapseSize):
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
		self.service = "Processor Report"

	def kill(self):
		self.terminate = True
      
	def run(self):
		cpuDataList = CircularList(self.timeLapseSize)
		while True:
			
			if self.terminate:
				return
			
			sendTime = self.sendRate
			while sendTime >= 0:
				sendTime -= 1
				cpu_quantity = 0
				cpu_percent = 0
				cpu_quantity = cpu_quantity + 1
				cpuDataList.Append(psutil.cpu_percent(self.refreshRate, percpu=False))
			
			formatedData = dataFormater(cpuDataList.GetList(), self.formatList)
			
			#example:
			#printf "%s\t%s\t%s\t%s\n" "192.168.0.100" "CPU Load" "0" "Status information|cpu1=50%;90;95;0;100" | ~/downloads/nsca-2.7.2/src/send_nsca -H 192.168.0.100 -c ~/downloads/nsca-2.7.2/sample-config/send_nsca.cfg
			
			message = "cpu load:" + str(formatedData)
			message += "|"
			message += messageFormater(formatedData, self.formatList, "proc", "%", self.warn, self.crit, self.mini)
				
			sendReport(self.destination, self.service, "0", message)

class networkReporter(Thread):
	'''thread class to collect and report network data'''
	def __init__ (self, refreshRate, sendRate, destination, formatList, timeLapseSize):
		Thread.__init__(self)
		self.terminate = False
		self.refreshRate = refreshRate
		self.sendRate = sendRate
		self.destination = destination
		self.formatList = formatList
		self.timeLapseSize = timeLapseSize
		self.warn = 400
		self.crit = 900
		self.mini = 0
		self.service = "Network Report"
		      
	def kill(self):
		self.terminate = True
	
	def run(self):
		sentDataList = CircularList(self.timeLapseSize)
		receivedDataList = CircularList(self.timeLapseSize)
		while True:
			
			if self.terminate:
				return
			
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
			
			message = " Received data " + str(formatedReceivedData) + " Sent data " + str(formatedSentData)
			message = "sent traffic:" + str(formatedSentData) + " received traffic:" + str(formatedReceivedData)
			message += "|"
			message += messageFormater(formatedReceivedData, self.formatList, "recv", "kbps", self.warn, self.crit, self.mini)
			message += messageFormater(formatedSentData, self.formatList, "sent", "kbps", self.warn, self.crit, self.mini)
			
			sentState = int(checkStatus(formatedSentData, self.crit, self.warn))
			recvState = int(checkStatus(formatedReceivedData, self.crit, self.warn))
			
			state = "3"
			if sentState > recvState:
				state = str(sentState)
			else:
				state = str(recvState)
			
			sendReport(self.destination, self.service, state, message)
	
def main_loop():
	'''main loop to call all the reporters'''
	
	#temporary parameters definition
	destination = "143.54.12.174"
	threadsList = []
	refreshRate = 0.1 #seconds
	sendRate = 20 #ticks -> relative to the refreshRate parameter
	formatList = [3,15,60]
	timeLapseSize = 60
	
	#here we should have the main call to the reporter threads
	
	#networkReporter thread
	current = networkReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	
	#processorReporter thread
	current = processorReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	
	#memoryReporter thread
	current = memoryReporter(refreshRate, sendRate, destination, formatList, timeLapseSize)
	threadsList.append(current)
	
	#processesAnalyzer thread
	current = processesAnalyzer(1)
	threadsList.append(current)
	
	#start every thread
	for reporterThread in threadsList:
		reporterThread.start()
	
	raw_input("Press Enter to kill all threads...")

	#send kill sign to all threads
	for reporterThread in threadsList:
		reporterThread.kill()
	
	#wait for each thread to finish
	for reporterThread in threadsList:
		reporterThread.join()
	
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
		main_loop()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == '__main__':
    main()

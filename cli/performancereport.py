#!/usr/bin/python

import sys
import os
if os.name != 'posix':
    sys.exit('platform not supported')
os.environ['PATH'] += ':/usr/bin:/sbin:/bin'
import atexit
import time
import commands
import re
import string
import argparse
from threading import Thread

import psutil

# Exit statuses recognized by Nagios
NAGIOS_OK = 0
NAGIOS_WARNING = 1
NAGIOS_CRITICAL = 2
NAGIOS_UNKNOWN = 3

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

def messageFormater(data_list, format_list, service_name, format_multiplier, unit, warning, critical, minimum, maximum=None):
    '''format a message given the data, service_name and parameters desired'''
    message = ""
    for format, data in zip(format_list, data_list) :
        message += service_name + str(format * format_multiplier) + "=" + "%.2f" % (data) \
            + unit + ";" + str(warning) + ";" + str(critical) + ";"  + str(minimum) \
            + ";" + (str(maximum) if maximum != None else "") + " "
    return message
    #example:
    #load1=0.040;5.000;10.000;0; load5=0.010;4.000;6.000;0; load15=0.000;3.000;4.000;0;
    
def dataFormater(data_list, formats):
    '''receives a data list and a format list returning the medium value until de Nth position of the data list for each format item'''
    return [data_list.average(n) for n in formats]
    
def checkStatus(level_list, critical, warning):
    worst_case = max(level_list)
    if worst_case >= critical:
        return NAGIOS_CRITICAL
    elif worst_case >= warning:
        return NAGIOS_WARNING
    else:
        return NAGIOS_OK

class CircularList:
    def __init__(self, size):
        self.list = [0] * size
        
    def append(self, data):
        self.list = [data] + self.list[:-1]
        
    def average(self, n):
        return sum(self.list[:n])/n

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

    

class Sender(Thread):
    def __init__(self, config, reporters):
        Thread.__init__(self)
        self.config = config
        self.reporters = reporters
        self.terminate = False

    def kill(self):
        self.terminate = True

    def threadLoop(self):
        for reporter in self.reporters:
            service = reporter.service
            message, state = reporter.data()
            self.__sendReport(service, state, message)
    
    def run(self):
        while not self.terminate:
            time.sleep(self.config.send_rate)
            self.threadLoop()
    
    def __sendReport(self, service, state, message):
        '''send report to nagios server'''
        #mount data 
        send_nsca_dir = "/usr/local/nagios/bin"
        send_nsca_cfg_dir = "/usr/local/nagios/etc"
        command = (
            "/usr/bin/printf \"%s\t%s\t%s\t%s\n\" \"" 
            + self.config.hostname + "\" \"" 
            + service + "\" \"" 
            + str(state) + "\" \"" 
            + message + "\" | " 
            + send_nsca_dir + "/send_nsca -H " 
            + self.config.nagios_server + " -c " 
            + send_nsca_cfg_dir + "/send_nsca.cfg")
        commandoutput = commands.getoutput(command)
        if self.config.debug:
            print "---------------------------------"
            print service, state, message
            print command

class Reporter(Thread):
    '''base reporter thread class'''
    def __init__ (self, config):
        Thread.__init__(self)
        self.terminate = False
        self.config = config
        self.minimum = 0
        self.maximum = None
    
    def kill(self):
        #send kill sign to terminate the thread in the next data collection loop
        self.terminate = True
        
    def threadLoop(self):
        #nothing on the base class 
        #Should be implemented by each reporter service and set the self.state and self.message variables
        return
            
    def run(self):
        while not self.terminate:
            #call method that actually do what the threads needs to do
            self.threadLoop()

class MemoryReporter(Reporter):
    '''reporter class to collect and report memory data'''
    def __init__(self, config):
        Reporter.__init__(self, config)
        self.service = "Memory Report"
        self.memDataList = CircularList(self.config.num_samples)
        self.maximum = psutil.phymem_usage().total / (1024 * 1024)
        
    def threadLoop(self):
        time.sleep(self.config.refresh_rate)
        #self.memDataList.append(psutil.phymem_usage().used / (1024 * 1024))
        self.memDataList.append((psutil.phymem_usage().percent * self.maximum) / 100)
        
    def data(self):
        formattedData = dataFormater(self.memDataList, self.config.data_intervals)
        # message mount
        warning = (self.config.memory_warning * self.maximum) / 100
        critical = (self.config.memory_critical * self.maximum) / 100
        message = "Memory usage: %dMB of %dMB (%d%%)" % (formattedData[0], \
            self.maximum, (formattedData[0] * 100) / self.maximum) \
            + "|" + messageFormater(formattedData, self.config.data_intervals, \
                    "muse", self.config.refresh_rate, "MB", warning, critical, \
                    self.minimum, self.maximum)
        # state mount
        state = checkStatus(formattedData, critical, warning)
        return message, state

class DiskReporter(Reporter):
    def __init__(self, config):
        Reporter.__init__(self, config)
        self.service = "Disk Report"
        self.list = CircularList(self.config.num_samples)
        self.maximum = psutil.disk_usage('/').total / (1024 * 1024 * 1024)
    
    def threadLoop(self):
        time.sleep(self.config.refresh_rate)
        self.list.append((psutil.disk_usage('/').percent * self.maximum) / 100)
        
    def data(self):
        formattedData = dataFormater(self.list, self.config.data_intervals)
        # message mount
        warning = (self.config.disk_warning * self.maximum) / 100
        critical = (self.config.disk_critical * self.maximum) / 100
        message = "Disk usage: %dGB of %dGB (%d%%)" % (formattedData[0], \
            self.maximum, (formattedData[0] * 100) / self.maximum) \
            + "|" + messageFormater(formattedData, self.config.data_intervals, \
                    "disk", self.config.refresh_rate, "GB", warning, critical, \
                    self.minimum, self.maximum)
        # state mount
        state = checkStatus(formattedData, critical, warning)
        return message, state

class ProcessorReporter(Reporter):
    '''reporter class to collect and report processor data'''
    def __init__ (self,config):
        Reporter.__init__(self, config)
        self.service = "Processor Report"
        self.cpuDataList = CircularList(self.config.num_samples)
        
    def threadLoop(self):
        self.cpuDataList.append(psutil.cpu_percent(self.config.refresh_rate, percpu=False))
    
    def data(self):
        formattedData = dataFormater(self.cpuDataList, self.config.data_intervals)
        # message mount
        message = ("CPU usage: %.1f%%" % formattedData[0] 
            + "|" + messageFormater(formattedData, self.config.data_intervals, \
                    "proc", self.config.refresh_rate, "%", \
                    self.config.cpu_warning, self.config.cpu_critical, \
                    self.minimum))
        # state mount
        state = checkStatus(formattedData, self.config.cpu_critical, \
            self.config.cpu_warning)
        return message, state

class NetworkReporter(Reporter):
    '''reporter class to collect and report network data'''
    def __init__(self, config):
        Reporter.__init__(self, config)
        self.service = "Network Report"
        self.sent = CircularList(self.config.num_samples)
        self.recv = CircularList(self.config.num_samples)
        
    def threadLoop(self):
        #timestamp_before = int(round(time.time() * 1000))
        #collect data
        #tot_before = psutil.network_io_counters()
        pnic_before = psutil.network_io_counters(pernic=True)
        stats_before = pnic_before[self.config.network_interface]

        while not self.terminate:
            time.sleep(self.config.refresh_rate)

            #tot_after = psutil.network_io_counters()
            pnic_after = psutil.network_io_counters(pernic=True)
            stats_after = pnic_after[self.config.network_interface]

            # format bytes to string
            bytesSent = toKbps(stats_after.bytes_sent - stats_before.bytes_sent) / self.config.refresh_rate
            bytesReceived = toKbps(stats_after.bytes_recv - stats_before.bytes_recv) / self.config.refresh_rate
            # store on a circular list
            self.sent.append(bytesSent)
            self.recv.append(bytesReceived)
            stats_before = stats_after
            
    def data(self):
        formatedSentData = dataFormater(self.sent, self.config.data_intervals)
        formatedReceivedData = dataFormater(self.recv, self.config.data_intervals)
        # message mount
        message = ("Network bandwidth used: up %.1fkbps - down %.1fkbps" \
            % (formatedSentData[0], formatedReceivedData[0]) + " |" \
            + messageFormater(formatedReceivedData, self.config.data_intervals, "recv", self.config.refresh_rate, "kbps", self.config.network_warning, self.config.network_critical, self.minimum) \
            + messageFormater(formatedSentData, self.config.data_intervals, "sent", self.config.refresh_rate, "kbps", self.config.network_warning, self.config.network_critical, self.minimum))
        # state mount
        state = max(int(checkStatus(formatedSentData, self.config.network_critical, self.config.network_warning)),
            int(checkStatus(formatedReceivedData, self.config.network_critical, self.config.network_warning)))
        return message, state

def parse_args():
    parser = argparse.ArgumentParser(description = "Fetches information for a Performance Reporter")
    parser.add_argument("--network_interface",
        required = False,
        help = "network interface to be monitored",
        dest = "network_interface",
        default = "eth0",
        metavar = "<network_interface>")
    parser.add_argument("--hostname",
        required = False,
        help = "name of the caller host",
        dest = "hostname",
        default = "`ifconfig  | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{ print $1}'`",
        metavar = "<hostname>")
    parser.add_argument("--intervals",
        required = False,
        help = "intervals list that the data should be collected as average. Example: 3,15,60",
        dest = "data_intervals",
        default = "3,15,60",
        metavar = "<data_intervals>")
    parser.add_argument("--send_rate",
        required = False,
        help = "set the interval in which the script will send data to the Nagios server, in seconds",
        dest = "send_rate",
        default = "60",
        metavar = "<send_rate>")
    parser.add_argument("--server",
        required = True,
        help = "IP address of the Nagios server",
        dest = "nagios_server",
        metavar = "<nagios_server>")
    parser.add_argument("--debug",
        required = False,
        help = "debug mode: print output",
        dest = "debug",
        action = "store_true")
    parser.add_argument("--network-warning", required=False, default="70000",
        help="define the warning limit in kbps", dest="network_warning", 
        metavar="<network_warning>")
    parser.add_argument("--network-critical", required=False, default="90000", 
        help="define the critical limit in kbps", dest="network_critical", 
        metavar="<network_critical>")
    parser.add_argument("--cpu-warning", required=False, default="90", 
        help="define the warning limit in %", dest="cpu_warning", 
        metavar="<cpu_warning>")
    parser.add_argument("--cpu-critical", required=False, default="100", 
        help="define the critical limit in %", dest="cpu_critical", 
        metavar="<cpu_critical>")
    parser.add_argument("--memory-warning", required=False, default="70", 
        help="define the warning limit in %", dest="memory_warning", 
        metavar="<memory_warning>")
    parser.add_argument("--memory-critical", required=False, default="90", 
        help="define the critical limit in %", dest="memory_critical", 
        metavar="<memory_critical>")
    parser.add_argument("--disk-warning", required=False, default="80", 
        help="define the warning limit in %", dest="disk_warning", 
        metavar="<disk_warning>")
    parser.add_argument("--disk-critical", required=False, default="90", 
        help="define the critical limit in %", dest="disk_critical", 
        metavar="<disk_critical>")
    return parser.parse_args()

class Configuration:
    def __init__(self, args):
        self.debug = args.debug
        self.network_interface = args.network_interface
        self.hostname = args.hostname
        self.nagios_server = args.nagios_server
        self.send_rate = int(args.send_rate)
        self.data_intervals = [int(x) for x in args.data_intervals.split(',')]
        # calculate new refresh rate with de greatest commom divisor
        self.refresh_rate = recgcd(self.data_intervals + [self.send_rate])
        # ajust each time interval according to the new time resolution
        self.data_intervals = [x/self.refresh_rate for x in self.data_intervals]
        # set circular list size according to maximum data resolution
        self.num_samples = max(self.data_intervals)
        self.network_warning = int(args.network_warning)
        self.network_critical = int(args.network_critical)
        self.cpu_warning = int(args.cpu_warning)
        self.cpu_critical = int(args.cpu_critical)
        self.memory_warning = int(args.memory_warning)
        self.memory_critical = int(args.memory_critical)
        self.disk_warning = int(args.disk_warning)
        self.disk_critical = int(args.disk_critical)

def main_loop(args):
    '''main loop to call all the reporters'''
    threadsList = []
    
    config = Configuration(args)
    
    # here we should have the main call to the reporter threads
    threadsList.append(NetworkReporter(config))
    threadsList.append(ProcessorReporter(config))
    threadsList.append(MemoryReporter(config))
    threadsList.append(DiskReporter(config))
    #processesAnalyzer thread
#    threadsList.append(processesAnalyzer(config))

    sender = Sender(config, threadsList)
    # start every thread
    for reporterThread in threadsList:
        reporterThread.start()

    sender.start()

    raw_input("Press Enter to kill all threads...\n")

    # send kill sign to all threads
    sender.kill()
    for reporterThread in threadsList:
        reporterThread.kill()
    # wait for each thread to finish
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

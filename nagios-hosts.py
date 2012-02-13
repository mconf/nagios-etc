#!/usr/bin/python

import os, sys, inspect, json
cmd_folder = os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0])
sys.path.append(cmd_folder + "/lib")
#cmd_folder += "/lib"
#sys.path.append(cmd_folder)
from pynag import Model
from pynag.Parsers import config

_DEBUG = False

if _DEBUG:
    hosts_cfg = 'hosts.cfg'
    nagios_cfg = 'nagios.cfg'
else:
    hosts_cfg = '/usr/local/nagios/etc/objects/hosts.cfg'
    nagios_cfg = '/usr/local/nagios/etc/nagios.cfg'

def print_usage():
    print "Usage:"
    print "   add <FreeSWITCH|BigBlueButton> <IP>"
    print "   remove <IP>"
    print "   reload"
    print "   force-reload"
    exit(0)

def check_hosts():
    if not os.path.exists(hosts_cfg):
        print "The text file defining the hosts doesn't exists"
        exit(1)
    return

def reload(forced=False):
    check_hosts();
    last_modified = int(os.path.getmtime(hosts_cfg) * 1000)

#    last_modified_filename = "updatehosts.tmp"
    last_modified_filename = cmd_folder + "/updatehosts.tmp"
    if os.path.exists(last_modified_filename):
        last_modified_file = open(last_modified_filename, "r")
        last_modified_stored = int(last_modified_file.readline())
        last_modified_file.close()
    else:
        last_modified_stored = last_modified

    if last_modified != last_modified_stored or forced:
        print "Reloading Nagios configuration"
        os.system("killall -HUP nagios")
    else:
        print "Unmodified content"

    last_modified_file = open(last_modified_filename, "w")
    last_modified_file.write("%d\n" % last_modified)
    last_modified_file.close()

def add(server_type, ip):
    server_type = server_type.lower()
    if server_type == 'bigbluebutton':
        hostgroup_name = 'bigbluebutton-servers'
        alias = 'BigBlueButton servers'
    elif server_type == 'freeswitch':
        hostgroup_name = 'freeswitch-servers'
        alias = 'FreeSWITCH servers'
    else:
        print 'Invalid server type'
        return
        
    nc = config(nagios_cfg)
    nc.parse()
#    print json.dumps(nc.data)
    if nc.get_host(ip) != None:
        print "Host is already there"
        return
 
    new_host = nc.get_new_item('host', hosts_cfg)
    new_host['use'] = 'generic-passive-host'
    new_host['host_name'] = ip
    new_host['address'] = ip
    new_host['meta']['needs_commit'] = True
    nc.data['all_host'].append(new_host)

    hostgroup = nc.get_hostgroup(hostgroup_name)
    if hostgroup == None:
        hostgroup = nc.get_new_item('hostgroup', hosts_cfg)
        hostgroup['hostgroup_name'] = hostgroup_name
        hostgroup['alias'] = alias
        hostgroup['members'] = ip
        
        allservers_hostgroup = nc.get_hostgroup('all-servers')
        if allservers_hostgroup == None:
            allservers_hostgroup = nc.get_new_item('hostgroup', hosts_cfg)
            allservers_hostgroup['hostgroup_name'] = 'all-servers'
            allservers_hostgroup['alias'] = 'All servers'
            allservers_hostgroup['members'] = hostgroup_name
        else:
            if len(allservers_hostgroup['members']) == 0:
                members = []
            else:
                members = allservers_hostgroup['members'].split(',')
            members.append(host_name)
            allservers_hostgroup['members'] = ','.join(members)
        allservers_hostgroup['meta']['needs_commit'] = True
    else:
        if len(hostgroup['members']) == 0:
            members = []
        else:
            members = hostgroup['members'].split(',')
        members.append(ip)
        hostgroup['members'] = ','.join(members)
    hostgroup['meta']['needs_commit'] = True

    nc.commit()
    return
    
def remove(ip):
    nc = config(nagios_cfg)
    nc.parse()
#    print json.dumps(nc.data)
    host = nc.get_host(ip)
    if host == None:
        print "Cannot find the host specified"
        return

    host['meta']['delete_me'] = True
    host['meta']['needs_commit'] = True
    
    for hostgroup in nc.data['all_hostgroup']:
        if not hostgroup.has_key('members'):
            continue
            
        members = hostgroup['members'].split(',')
        if ip in members:           
            members = [x for x in members if x != ip]
            hostgroup['members'] = ','.join(members)
            hostgroup['meta']['needs_commit'] = True
    
    nc.commit()
    return

if len(sys.argv) == 1:
    print_usage()

if sys.argv[1] == "reload":
    reload()
elif sys.argv[1] == "add":
    if len(sys.argv) != 4:
        print_usage()
    else:
        add(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "remove":
    if len(sys.argv) != 3:
        print_usage()
    else:
        remove(sys.argv[2])
elif sys.argv[1] == "force-reload":
    reload(True)
else:
    print_usage();


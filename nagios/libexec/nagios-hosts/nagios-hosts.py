#!/usr/bin/python

import os, sys, inspect, json
cmd_folder = os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0])
from pynag import Model
from pynag.Parsers import config
from urlparse import urlparse

_DEBUG = False

if _DEBUG:
    hosts_cfg = '/home/felipe/codes/nagios-etc/etc/objects/mconf/hosts.cfg'
    nagios_cfg = '/home/felipe/codes/nagios-etc/etc/nagios.cfg'
else:
    hosts_cfg = '/usr/local/nagios/etc/objects/mconf/hosts.cfg'
    nagios_cfg = '/usr/local/nagios/etc/nagios.cfg'

def print_usage():
    print "Usage:"
    print "   add <freeswitch|bigbluebutton> <HOST> [<SALT>]"
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

def get_nagios_data():
    nc = config(nagios_cfg)
    nc.parse()
    # crash if there's no data on nc.data
    if nc.data == None:
	nc.data = {}
    if not nc.data.has_key('all_host'):
	nc.data['all_host'] = []
    if not nc.data.has_key('all_hostgroup'):
        nc.data['all_hostgroup'] = []
    return nc

def add(server_type, host, salt=''):
    server_type = server_type.lower()
    if server_type == 'bigbluebutton':
        hostgroup_name = 'bigbluebutton-servers'
        alias = 'BigBlueButton servers'
        ip = urlparse(host).hostname
    elif server_type == 'freeswitch':
        hostgroup_name = 'freeswitch-servers'
        alias = 'FreeSWITCH servers'
        ip = host
    else:
        print 'Invalid server type'
        return
        
    nc = get_nagios_data()
    if nc.get_host(ip) != None:
        print "Host is already there, so it will deleted before continue"
        remove_host(ip)
        nc = get_nagios_data()
 
    #host_name = "%s %s" % (server_type, ip)
    host_name = ip
    new_host = nc.get_new_item('host', hosts_cfg)
    new_host['use'] = 'generic-passive-host'
    new_host['host_name'] = host_name
    new_host['address'] = host_name
    new_host['meta']['needs_commit'] = True
    if server_type == 'bigbluebutton':
        new_host['_bbb_url'] = host
        new_host['_bbb_salt'] = salt
        new_host['_lb_disabled'] = 1
    nc.data['all_host'].append(new_host)

    hostgroup = nc.get_hostgroup(hostgroup_name)
    if hostgroup == None:
        hostgroup = nc.get_new_item('hostgroup', hosts_cfg)
        hostgroup['hostgroup_name'] = hostgroup_name
        hostgroup['alias'] = alias
        hostgroup['members'] = ''
        nc.data['all_hostgroup'].append(hostgroup)
        
        allservers_hostgroup = nc.get_hostgroup('all-servers')
        if allservers_hostgroup == None:
            allservers_hostgroup = nc.get_new_item('hostgroup', hosts_cfg)
            allservers_hostgroup['hostgroup_name'] = 'all-servers'
            allservers_hostgroup['alias'] = 'All servers'
            allservers_hostgroup['members'] = 'localhost'
            allservers_hostgroup['hostgroup_members'] = ''
            nc.data['all_hostgroup'].append(allservers_hostgroup)
        if not allservers_hostgroup.has_key('hostgroup_members'):
            allservers_hostgroup['hostgroup_members'] = ''
        allservers_hostgroup['hostgroup_members'] = add_member(allservers_hostgroup['hostgroup_members'], hostgroup_name)
        allservers_hostgroup['meta']['needs_commit'] = True
    hostgroup['members'] = add_member(hostgroup['members'], host_name)
    hostgroup['meta']['needs_commit'] = True
    
    nc.commit()
    return
    
def remove_group(nc, hostgroup_name):
    for hostgroup in nc.data['all_hostgroup']:

        if hostgroup['hostgroup_name'] == hostgroup_name:
            hostgroup['meta']['delete_me'] = True
            hostgroup['meta']['needs_commit'] = True
        else:
            if not hostgroup.has_key('hostgroup_members'):
                continue
            if has_member(hostgroup['hostgroup_members'], hostgroup_name):
                hostgroup['hostgroup_members'] = remove_member(hostgroup['hostgroup_members'], hostgroup_name)
                hostgroup['meta']['needs_commit'] = True
            if len(hostgroup['hostgroup_members']) == 0:
                del hostgroup['hostgroup_members']
                if not hostgroup.has_key('members'):
                    remove_group(nc, hostgroup['hostgroup_name'])
    
def add_member(members, new_member):
    if members == None or len(members) == 0:
        return new_member
    else:
        members = members.split(',')
        members.append(new_member)
        return ','.join(members)

def remove_member(members, member_to_remove):
    if len(members) == 0:
        return ''
    members = members.split(',')
    if member_to_remove in members:
        members = [x for x in members if x != member_to_remove]
    return ','.join(members)

def has_member(members, member_to_test):
    return len(members) != len(remove_member(members, member_to_test))

def remove_host(host_name):
    nc = get_nagios_data()
    host = nc.get_host(host_name)
    if host == None:
        print "Cannot find the host specified"
        return

    host['meta']['delete_me'] = True
    host['meta']['needs_commit'] = True
    
    for hostgroup in nc.data['all_hostgroup']:
        if not hostgroup.has_key('members'):
            continue

        if has_member(hostgroup['members'], host_name):
            hostgroup['members'] = remove_member(hostgroup['members'], host_name)
            hostgroup['meta']['needs_commit'] = True
            if len(hostgroup['members']) == 0:
                del hostgroup['members']
                remove_group(nc, hostgroup['hostgroup_name'])

    nc.commit()
    return

if len(sys.argv) == 1:
    print_usage()

if sys.argv[1] == "reload":
    reload()
elif sys.argv[1] == "add":
    if len(sys.argv) < 4:
        print_usage()
    else:
        if sys.argv[2] == 'bigbluebutton':
            if len(sys.argv) != 5:
                print_usage()
            else:
                add(sys.argv[2], sys.argv[3], sys.argv[4])
        else:
            add(sys.argv[2], sys.argv[3])
elif sys.argv[1] == "remove":
    if len(sys.argv) != 3:
        print_usage()
    else:
        remove_host(sys.argv[2])
elif sys.argv[1] == "force-reload":
    reload(True)
else:
    print_usage();


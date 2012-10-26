#!/usr/bin/python
# -*- coding: utf-8 -*

import os
import sys
import inspect
import json
import re
import pynag.Model
from pynag.Model import AttributeList
from pynag.Parsers import config
from urlparse import urlparse
from pprint import pprint

_DEBUG = False

if _DEBUG:
    hosts_cfg = '../../etc/objects/mconf/hosts.cfg'
    nagios_cfg = '../../etc/nagios.cfg'
else:
    hosts_cfg = '/usr/local/nagios/etc/objects/mconf/hosts.cfg'
    nagios_cfg = '/usr/local/nagios/etc/nagios.cfg'

hostgroups = [ 'mconf-live-servers', 'temporary-servers', 'mconf-network-members' ]

def print_usage():
    print "Usage:"
    print "   add <SERVER_URL> <SALT>"
    print "   remove <HOSTNAME>"
    print "   detail <HOSTNAME>"
    print "   add-to-network <HOSTNAME>"
    print "   remove-from-network <HOSTNAME>"
    print "   list <%s>" % (' | '.join(hostgroups))
    print "   update-metadata <JSON_FILE>"
    print "   clean"
    print "   reload"
    print "   force-reload"
    exit(0)

def reload(forced=False):
    last_modified = int(os.path.getmtime(hosts_cfg) * 1000)

#    last_modified_filename = "updatehosts.tmp"
    last_modified_filename = "/tmp/mconf-updatedhosts.tmp"
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

def add_host(url, salt):
    url = url.lower()
    address = urlparse(url).netloc
    address_split = address.split(':')
    if len(address_split) > 1:
        port = address_split[1]
    else:
        port = 80
    hostname = address_split[0]
    if not (hostname and len(hostname) > 0 and hostname != "localhost"):
        print "==> Invalid hostname!"
        return
    
    host = None
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        if host:
            print "==> Filtered by host_name"
    except:
        pass

    duplicates = []
    if not host:
        hosts = pynag.Model.Host.objects.filter(_bbb_salt=salt)
        if hosts:
            for host in hosts:
                print "==> Host %s has the same server salt, deleting it" % (host['host_name'])
                if host.has_key('_duplicates'):
                    duplicates += host['_duplicates'].split(',')
                duplicates.append(host['host_name'])
                host.delete()
            host = None
        
    if not host:
        host = pynag.Model.Host()
        host.attribute_appendfield('hostgroups', 'mconf-live-servers')
        host.attribute_appendfield('hostgroups', 'temporary-servers')
        print "==> Created a new host"

    host['use'] = 'generic-passive-host'
    host['host_name'] = hostname
    host['address'] = hostname
    host['_bbb_salt'] = salt
    host['_bbb_url'] = url
    host['_bbb_port'] = port
    if len(duplicates) > 0:
        # remove from the duplicates the current hostname
        if hostname in duplicates:
            duplicates.remove(hostname)
        # removes duplicates from the list
        host['_duplicates'] = ','.join(list(set(duplicates)))

    print host
    host.set_filename(hosts_cfg)
    host.save()
    print "==> Added!"

def remove_host(hostname):
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        print host
        host.delete()
        print "==> Removed!"
    except KeyError:
        print "==> Can't find the host %s" % (hostname)
        
def list_hosts(hostgroup=None):
    if not hostgroup:
        hosts = pynag.Model.Host.objects.all
    elif not hostgroup in hostgroups:
        print "==> %s is not a valid hostgroup" % (hostgroup)
        return
    else:
        hosts = [host['host_name'] for host in pynag.Model.Host.objects.filter(hostgroups__contains=hostgroup)]
    hosts.sort()
    print hosts

def detail_host(hostname=None):
    if not hostname:
        for host in pynag.Model.Host.objects.all:
            print host
        return
        
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        print host
        print "==> Details printed!"
    except KeyError:
        print "==> Can't find the host %s" % (hostname)

def add_to_network(hostname):
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        host.attribute_replacefield('hostgroups', 'temporary-servers', 'mconf-network-members')
        host.save()
        print host
        print "==> Host added to the network!"
    except KeyError:
        print "==> Can't find the host %s" % (hostname)
    
def remove_from_network(hostname):
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        host.attribute_replacefield('hostgroups', 'mconf-network-members', 'temporary-servers')
        host.save()
        print host
        print "==> Host added to the network!"
    except KeyError:
        print "==> Can't find the host %s" % (hostname)

def update_metadata(json_file):
    json_data = open(json_file)
    data = json.load(json_data)
    
    url = data['metadata']['server_url'].lower()
    # do not add the server_url again
    del data['metadata']['server_url']
    if not url.startswith('http://'):
        url = 'http://' + url
    address = urlparse(url).netloc
    hostname = address.split(':')[0]
    
    try:
        host = pynag.Model.Host.objects.get_by_shortname(hostname)
        for attr in data['metadata'].iterkeys():
            host['_' + attr] = data['metadata'][attr]
        print host
        host.save()
        print "==> Updated host metadata!"
    except KeyError:
        print "==> Can't find the host %s" % (hostname)
    
    json_data.close()
    return

def clean():
    for host in pynag.Model.Host.objects.filter(_bbb_salt__exists=True):
        url = host['_bbb_url']
        salt = host['_bbb_salt']
        try:
            host.delete()
        except:
            pass
        add_host(url, salt)

if __name__ == '__main__':
    pynag.Model.cfg_file = nagios_cfg

    if not os.path.exists(hosts_cfg):
        print "The text file defining the hosts doesn't exists"
        exit(1)

    if len(sys.argv) == 1:
        print_usage()
    if sys.argv[1] == "reload":
        reload(False)
    elif sys.argv[1] == "add":
        add_host(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "remove":
        remove_host(sys.argv[2])
    elif sys.argv[1] == "detail":
        detail_host(sys.argv[2] if len(sys.argv) > 2 else None)
    elif sys.argv[1] == "list":
        list_hosts(sys.argv[2] if len(sys.argv) > 2 else None)
    elif sys.argv[1] == "add-to-network":
        add_to_network(sys.argv[2])
    elif sys.argv[1] == "remove-from-network":
        remove_from_network(sys.argv[2])
    elif sys.argv[1] == "update-metadata":
        update_metadata(sys.argv[2])
    elif sys.argv[1] == "clean":
        clean()
    elif sys.argv[1] == "force-reload":
        reload(True)
    else:
        print_usage();


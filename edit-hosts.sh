#!/bin/bash

sudo vim /usr/local/nagios/etc/objects/mconf/hosts.cfg
sudo /usr/bin/python /usr/local/nagios/libexec/mconf-hosts/mconf-hosts.py reload

#!/bin/bash

cat /usr/local/nagios/etc/objects/mconf/hosts.cfg | grep -v '#.*\|^$' | sed 's:}:}\n:g' > hosts.cfg.tmp
sudo mv hosts.cfg.tmp /usr/local/nagios/etc/objects/mconf/hosts.cfg

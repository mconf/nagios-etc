#!/bin/bash

cp nagios/etc/objects/mconf/hosts.cfg nagios/etc/objects/mconf/hosts.cfg.backup
cat nagios/etc/objects/mconf/hosts.cfg | grep -v '#.*\|^$' | sed 's:}:}\n:g' > hosts.cfg.tmp
sudo mv hosts.cfg.tmp nagios/etc/objects/mconf/hosts.cfg

#!/bin/bash

cp -r /usr/local/nagios/etc/objects/mconf/* etc/objects/mconf/
cp -r /usr/local/nagios/libexec/bigbluebutton/* libexec/bigbluebutton/
cp -r /usr/local/nagios/libexec/nagios-hosts/* libexec/nagios-hosts/
cp /etc/nagiosgraph/datasetdb.conf /etc/nagiosgraph/labels.conf /etc/nagiosgraph/nagiosgraph.conf /etc/nagiosgraph/ngshared.pm /etc/nagiosgraph/rrdopts.conf nagiosgraph/


#!/bin/bash

ORIG="/usr/local/nagios/etc/objects/mconf/hosts.cfg"
CURRENT_BACKUP="hosts`date '+%Y%m%d-%H%M%S'`.cfg"
BACKUP_PATH="/home/nagios"

if [ `find $BACKUP_PATH -name 'hosts*.cfg' | wc -l` -eq 0 ]
then
	cp $ORIG $BACKUP_PATH/$CURRENT_BACKUP
fi

LAST_BACKUP="`find $BACKUP_PATH -name 'hosts*.cfg' | sort -r | head -n 1`"
if [ `diff $ORIG $LAST_BACKUP | wc -l` -gt 0 ]
then
	cp $ORIG $BACKUP_PATH/$CURRENT_BACKUP
fi


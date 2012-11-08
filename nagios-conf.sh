#!/bin/bash

function print_usage
{
	echo "Usage:"
	echo "    $0 <backup|deploy>"
	exit 1
}

if [ $# -ne 1 ]
then
	print_usage
fi

if [ $1 != "backup" ] && [ $1 != "deploy" ]
then
	print_usage
fi

function copy {
	dev_dir="$1"
	src_dir="$2"
	dst_dir="$3"
	for i in `find $dev_dir -type f -name '*' -exec echo {} \; | grep -v '.git' | grep -v '*~'`
	do
		file_src="$src_dir/$i"
		file_dst="$dst_dir/$i"
		echo "Copying $file_src to $file_dst"
		if [ -e "$file_src" ]
		then
			echo "OK!"
			mkdir -p $(dirname $file_dst)
			cp "$file_src" "$file_dst"
		fi
	done
}

if [ "$1" == "deploy" ]
then
	copy "nagios" "." "/usr/local"
	copy "nagiosgraph" "." "/etc"
	sudo chown -R nagios:nagios /usr/local/nagios
elif [ "$1" == "backup" ]
then
	copy "nagios" "/usr/local" "."
	copy "nagiosgraph" "/etc" "."
fi

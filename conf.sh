#!/bin/bash

function copy {
	dev_dir="$1"
	src_dir="$2"
	dst_dir="$3"
	for i in `find $dev_dir -type f -name '*' -exec echo {} \; | grep -v '.git'`
	do
		file_src="$src_dir/$i"
		file_dst="$dst_dir/$i"
		echo "Copying $file_src to $file_dst"
		if [ -e "$file_src" ]
		then
			echo "OK!"
			#cp "$file_src" "$file_dst"
		fi
	done
}

if [ "$1" == "deploy" ]
then
	copy "nagios" "." "/usr/local"
	copy "nagiosgraph" "." "/etc"
elif [ "$1" == "backup" ]
then
	copy "nagios" "/usr/local" "."
	copy "nagiosgraph" "/etc" "."
else
	echo "Invalid option!"
fi


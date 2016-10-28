#!/bin/bash

snapgit=`git log --pretty=oneline -n1|cut -c1-8`
snapser=`git log --pretty=oneline | wc -l`

makever=`make showversion`
basever=`echo ${makever} | cut -d. -f-2`

prefix=dpdk-${basever}-${snapser}.git${snapgit}
archive=${prefix}.tar.gz

echo "Creating ${archive}"
git archive --prefix=${prefix}/ HEAD  | gzip -9 > ${archive}

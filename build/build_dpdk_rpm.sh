#!/bin/bash

# Copyright (c) 2016 Open Platform for NFV Project, Inc. and its contributors
# Copyright (c) 2016 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

set -e

echo "==============================="
echo executing $0 $@
echo executing on machine `uname -a`

usage() {
    echo "$0 -g < [master] | [tag] | [commit] > -h -k -p < URL >        \
             -u < URL > -v                                              \
                                                                        \
    -g <DPDK TAG>   -- DPDK release tag commit to build. The default is \
                       master.                                          \
    -k              -- Build igb_uio kernel module                      \
    -h              -- print this message                               \
    -p <patch url>  -- Specify url to patches if required for ovs rpm.  \
    -v              -- Set verbose mode."
}
while getopts "g:hkp:u:v" opt; do
    case "$opt" in
        g)
            DPDK_VERSION=${OPTARG}
            ;;
        k)
            KMOD="yes"
            ;;
        h|\?)
            usage
            exit 1
            ;;
        p)
            DPDK_PATCH=${OPTARG}
            ;;
        u)
            DPDK_REPO_URL=${OPTARG}
            ;;
        v)
            verbose="yes"
            ;;
    esac
done

if [ -z $DPDK_REPO_URL ]; then
    DPDK_REPO_URL=http://dpdk.org/git/dpdk
fi
if [ -z $DPDK_VERSION ]; then
    DPDK_VERSION=master
fi

HOME=`pwd`
TOPDIR=$HOME
TMPDIR=$TOPDIR/rpms

function install_pre_reqs() {
    echo "----------------------------------------"
    echo Install dependencies for dpdk.
    echo
    sudo yum -y install gcc make python-devel openssl-devel kernel-devel graphviz \
                kernel-debug-devel autoconf automake rpm-build redhat-rpm-config \
                libtool python-twisted-core desktop-file-utils groff PyQt4          \
                libpcap-devel python-sphinx numactl-devel libvirt-devel
}

mkdir -p $TMPDIR

install_pre_reqs

RPMDIR=$HOME/rpmbuild
if [ -d $RPMDIR ]; then
    rm -rf $RPMDIR
fi
mkdir -p $RPMDIR/RPMS
mkdir -p $RPMDIR/SOURCES
mkdir -p $RPMDIR/SPECS
mkdir -p $RPMDIR/SRPMS


cd $TMPDIR
if [ ! -d dpdk ]; then
    git clone $DPDK_REPO_URL
    cd dpdk
else
    cd dpdk
    set +e
    make clean
    rm *.gz
    set -e
fi

if [[ "$DPDK_VERSION" =~ "master" ]]; then
    git checkout master
    snapgit=`git log --pretty=oneline -n1|cut -c1-8`
else
    git checkout v$DPDK_VERSION
fi

cp $HOME/dpdk-snap/* $RPMDIR/SOURCES
snapser=`git log --pretty=oneline | wc -l`

makever=`make showversion`
basever=`echo ${makever} | cut -d- -f1`
snapver=${snapser}.git${snapgit}


if [[ "$DPDK_VERSION" =~ "master" ]]; then
    prefix=dpdk-${basever}.${snapser}.git${snapgit}
    cp $HOME/dpdk-snap/dpdk.spec $TMPDIR/dpdk
    cp $HOME/dpdk-snap/dpdk.spec $RPMDIR/SOURCES
    cp $HOME/dpdk-snap/dpdk.spec $RPMDIR/SPECS
else
    prefix=dpdk-${basever:0:5}
    if [[ "$DPDK_PATCH"  =~ "yes" && "$DPDK_VERSION" =~ "16.11" ]]; then
        echo "----------------------------------------------"
        echo "Copy applicable patches."
        cp $TOPDIR/patches/$DPDK_VERSION/* $RPMDIR/SOURCES
        cp $HOME/dpdk-snap/dpdk.1611.spec $TMPDIR/dpdk/dpdk.spec
        cp $HOME/dpdk-snap/dpdk.1611.spec $RPMDIR/SPECS/dpdk.spec
        cp $HOME/dpdk-snap/dpdk.1611.spec $RPMDIR/SOURCES/dpdk.spec
    else
        cp $HOME/dpdk-snap/dpdk.spec $TMPDIR/dpdk
        cp $HOME/dpdk-snap/dpdk.spec $RPMDIR/SOURCES
        cp $HOME/dpdk-snap/dpdk.spec $RPMDIR/SPECS
    fi
fi
archive=${prefix}.tar.gz

echo "-------------------------------"
echo "Creating archive: ${archive}"
echo
git archive --prefix=${prefix}/ HEAD  | gzip -9 > ${archive}
cp ${archive} $RPMDIR/SOURCES/
echo "-------------------------------"
echo building RPM for DPDK version $DPDK_VERSION
echo
echo DPDK_VERSION is $DPDK_VERSION

if [[ "$DPDK_VERSION" =~ "master" ]]; then
    rpmbuild -bb -vv --define "_topdir $RPMDIR" --define "_snapver $snapver" --define "_ver $basever" dpdk.spec
else
    rpmbuild -bb -vv --define "_topdir $RPMDIR" --define "_ver $DPDK_VERSION" dpdk.spec
fi

#
# Copy all RPMs to build directory
#
echo Copy all RPMs to build directory
cd $RPMDIR
RPMS=$(find . -type f -iname '*.rpm')
SRPMS=$(find . -type f -iname '*.srpm')
SRCRPMS=$(find . -type f -name '*.src.rpm')

for i in $RPMS $SRPMS $SRCRPMS
do
    cp $i $HOME
done
exit 0

#!/bin/bash
#set -xe -o pipefail
echo "======================================"
echo executing $0
echo
# Check if we are running on Centos or Ubuntu
if [ -f /etc/lsb-release ];then
    cat /etc/lsb-release
    echo "======================================"
    echo "Ubuntu version: "
    . /etc/lsb-release
    sudo apt-get install rpm
    echo "Ubuntu is not supported for now."
    exit 0
elif [ -f /etc/redhat-release ];then
    echo "======================================"
    echo "redhat release version: "
    cat /etc/redhat-release
    echo
fi
export BASE_DIR=$(dirname $0)/../..

echo "======================================"
echo "BASE_DIR: ${BASE_DIR}"
echo "BUILD_DIR: ${BASE_DIR}/build"
echo
if [ ! -d ${BASE_DIR}/build ]; then
    echo "=================================="
    echo "${BASE_DIR}/build doesn't exist"
    echo
    exit 1
fi
cd ${BASE_DIR}/build/
if [ ! -e build.sh ]; then
    echo "=================================="
    echo "build.sh doesn't exist"
    echo
    exit 1
fi
echo ./build.sh
./build.sh

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
export BASE_DIR=$(dirname $0)/../rpm_dpdk

echo "======================================"
echo "BASE_DIR: ${BASE_DIR}"
echo
if [ -d ${BASE_DIR}/build ]; then
    cd ${BASE_DIR}/build/
    if [ -e build.sh ]; then
        ./build.sh
    fi
fi
#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log) 2>&1

apt-get update -y
apt-get install -y python3 python3-pip
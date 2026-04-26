#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log) 2>&1

apt-get update -y
apt-get install -y python3 python3-pip

mkdir -p /etc/systemd/system/k3s.service.d
cat > /etc/systemd/system/k3s.service.d/kubeconfig-permissions.conf << EOF
[Service]
ExecStartPost=/bin/chmod 644 /etc/rancher/k3s/k3s.yaml
EOF
systemctl daemon-reload
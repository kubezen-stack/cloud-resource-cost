#!/bin/bash

set -e
set -x

KUBERNETES_VERSION="${kubernetes_version}"
ENVIRONMENT="${environment}"
HOSTNAME_TAG="${hostname-tag}"

exec > >(tee /var/log/user-data.log) 
exec 2>&1

INSTANCE_ID=$(ec2-metadata --instance-id | cut -d ' ' -f2)
HOSTNAME="${HOSTNAME_TAG}-${INSTANCE_ID}"
hostnamectl set-hostname "${HOSTNAME}"
echo "127.0.0.1 ${HOSTNAME}" >> /etc/hosts

echo "[1] Updating system packages..."
DEBIAN_FRONTEND=noninteractive 
apt-get update -y
apt-get upgrade -y

echo "[2] Installing prerequisites..."
apt-get install -y \ 
        apt-transport-https \
        ca-certificates \
        curl \
        software-properties-common \
        jq \
        lsb-release \
        net-tools \
        git \
        gnupg \
        gpg \
        vim \
        unzip \
        htop

echo "[3] Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws

echo "[4] Disabling swap..."
swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab

echo "[5] Enabling kernel modules..."
cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

echo "[6] Set System Networking Parameters..."
cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
EOF
sysctl --system

echo "[7] Installing containerd..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y containerd.io

mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml > /dev/null
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

systemctl restart containerd
systemctl enable containerd

echo "[8] Installing Kubernetes components..."
mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | \
  gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] \
https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" | \
  tee /etc/apt/sources.list.d/kubernetes.list > /dev/null

apt-get update
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

echo "[9] Installing Docker..."
apt-get install -y docker-ce docker-ce-cli
usermod -aG docker ubuntu

if [ "${ENVIRONMENT}" == "production" ]; then
  echo "Installing Cloudwatch Agent..."
    wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
    dpkg -i amazon-cloudwatch-agent.deb
    rm -f amazon-cloudwatch-agent.deb
fi
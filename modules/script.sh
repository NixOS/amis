#!/usr/bin/env bash
set -e
set -o pipefail

token=$(curl --silent --retry 5 --fail-with-body -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 3600")

function imds() {
    curl --silent --retry 5 --fail-with-body -H "X-aws-ec2-metadata-token: $token" -s "http://169.254.169.254/$1"
}

imds latest/meta-data/public-keys/ | while read -r key; do
    imds "latest/meta-data/public-keys/$key/openssh-key" >> /home/ec2-user/.ssh/authorized_keys
done
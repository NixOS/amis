{ lib, modulesPath, config, pkgs, ... }:
{
  boot.kernelParams = [ "console=ttyS0,115200n8" ];
  boot.loader = {
    timeout = 10; # NOTE: For Debugging
    systemd-boot.enable = true;
  };

  security.sudo.wheelNeedsPassword = false;
  users.users.ec2-user = {
    isNormalUser = true;
    extraGroups = [ "wheel" ];
  };

  services.openssh.enable = true;

  systemd.services.print-ssh-host-keys = {
    description = "Print SSH host keys to console";
    after = [ "sshd.service" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      StandardOutput = "journal+console";
    };
    script = ''
      echo -----BEGIN SSH HOST KEY KEYS-----
      cat /etc/ssh/ssh_host_*_key.pub
      echo -----END SSH HOST KEY KEYS-----

      echo -----BEGIN SSH HOST KEY FINGERPRINTS-----
      for f in /etc/ssh/ssh_host_*_key.pub; do
        ${pkgs.openssh}/bin/ssh-keygen -l -f $f
      done
      echo -----END SSH HOST KEY FINGERPRINTS-----
    '';
  };

  systemd.services.ec2-metadata = {
    description = "Fetch EC2 metadata and set up ssh keys for ec2-user";
    after = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    serviceConfig = { Type = "oneshot"; };

    script = ''
      token=$(${pkgs.curl}/bin/curl --silent --show-error --fail-with-body --retry 20 --retry-connrefused  -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60") || exit 1
      function imds {
        ${pkgs.curl}/bin/curl --silent --show-error --fail-with-body --retry 20 --retry-connrefused --header "X-aws-ec2-metadata-token: $token"  "http://169.254.169.254/latest/$1"
      }
      if [ -e /home/ec2-user/.ssh/authorized_keys ]; then
        exit 0
      fi

      mkdir -p /home/ec2-user/.ssh
      chmod 700 /home/ec2-user/.ssh
      chown -R ec2-user:users /home/ec2-user/.ssh

      for i in $(imds meta-data/public-keys/); do
        imds "meta-data/public-keys/''${i}openssh-key" >> /home/ec2-user/.ssh/authorized_keys
      done

      chmod 600 /home/ec2-user/.ssh/authorized_keys
    '';
  };

  # Fetch from DHCP
  networking.hostName = lib.mkDefault "";
}

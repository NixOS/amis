{ selfPackages, config, pkgs, ... }:
{
  users.groups.ec2-instance-connect = { };
  users.users.ec2-instance-connect = {
    isSystemUser = true;
    group = "ec2-instance-connect";
  };

  # Ugly: sshd refuses to start if a store path is given because /nix/store is group-writable.
  # So indirect by a symlink.
  environment.etc."ssh/aws-ec2-instance-connect" = {
    mode = "0755";
    text = ''
      #!/bin/sh
      exec ${selfPackages.ec2-instance-connect}/bin/eic_run_authorized_keys "$@"
    '';
  };
  services.openssh = {
    authorizedKeysCommandUser = "ec2-instance-connect";
    authorizedKeysCommand = "/etc/ssh/aws-ec2-instance-connect %u %f";
  };
}

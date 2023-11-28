{ selfPackages, config, pkgs, ... }:
{
  users.groups.ec2-instance-connect = { };
  users.users.ec2-instance-connect = {
    isSystemUser = true;
    group = "ec2-instance-connect";
  };
  services.openssh = {
    authorizedKeysCommandUser = "ec2-instance-connect";
    authorizedKeysCommand = "${selfPackages.ec2-instance-connect}/bin/ec2-instance-connect %u %f";
  };
}

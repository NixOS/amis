{ selfPackages, pkgs, config, lib, ... }: {
  name = "ec2-metadata";

  nodes.machine = { lib, config, pkgs, ...}: {
    ec2.instanceType = "t4g.nano";
    ec2.ami = "ami-0d8f6eb4f641ef691";
  };

  testScript = ''
    machine.wait_for_unit("multi-user.target")
    machine.succeed("cat /home/ec2-user/.ssh/authorized_keys")
  '';

}

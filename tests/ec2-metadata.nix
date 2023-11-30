{ selfPackages, pkgs, config, lib, ... }: {
  name = "ec2-metadata";
  nodes.machine = { lib, config, pkgs, ... }: {
  };

  testScript = ''
    machine.start()
    machine.wait_for_unit("multi-user.target")
    machine.succeed("cat /home/ec2-user/.ssh/authorized_keys")
  '';

}

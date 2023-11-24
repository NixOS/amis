{
  name = "resize-partition";

  nodes.machine = { lib, config, pkgs, ... }: {
    imports = [ ../modules/amazon-image.nix];
    networking.hostName = lib.mkForce "";
  };

  testScript = { nodes, ... }: ''
    machine.start()
    machine.wait_for_unit("multi-user.target")
  '';
}

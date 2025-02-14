{
  name = "resize-partition";

  nodes.machine =
    {
      lib,
      config,
      pkgs,
      ...
    }:
    {
      virtualisation.directBoot.enable = false;
      virtualisation.mountHostNixStore = false;
      virtualisation.useEFIBoot = true;
      virtualisation.fileSystems = lib.mkForce { };
    };

  testScript =
    { nodes, ... }:
    ''
      import os
      import subprocess
      import tempfile

      tmp_disk_image = tempfile.NamedTemporaryFile()

      subprocess.run([
        "${nodes.machine.virtualisation.qemu.package}/bin/qemu-img",
        "create",
        "-f",
        "qcow2",
        "-b",
        "${nodes.machine.system.build.image}/${nodes.machine.image.repart.imageFile}",
        "-F",
        "raw",
        tmp_disk_image.name,
        "4G",
      ])

      # Set NIX_DISK_IMAGE so that the qemu script finds the right disk image.
      os.environ['NIX_DISK_IMAGE'] = tmp_disk_image.name

      machine.wait_for_unit("systemd-repart.service")
      # TODO: actually test if resize happened
      bootctl_status = machine.succeed("bootctl status")

    '';
}

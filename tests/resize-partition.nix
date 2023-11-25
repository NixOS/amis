{
  name = "resize-partition";

  nodes.machine = { lib, config, pkgs, ... }: {
    imports = [ ../modules/amazon-image.nix ];
    virtualisation.directBoot.enable = false;
    virtualisation.mountHostNixStore = false;
    virtualisation.useEFIBoot = true;

    networking.hostName = lib.mkForce "";
  };

  testScript = { nodes, ... }: ''
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
      "${nodes.machine.system.build.image}/image.raw",
      "-F",
      "raw",
      tmp_disk_image.name,
      "4G",
    ])

    # Set NIX_DISK_IMAGE so that the qemu script finds the right disk image.
    os.environ['NIX_DISK_IMAGE'] = tmp_disk_image.name

    machine.wait_for_unit("systemd-repart.service")
    systemd_repart_logs = machine.succeed("journalctl --unit systemd-repart.service")
    assert "Growing existing partition 1." in systemd_repart_logs

    bootctl_status = machine.succeed("bootctl status")

  '';
}

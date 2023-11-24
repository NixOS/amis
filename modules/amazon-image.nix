{ config, modulesPath, lib, pkgs, ... }:
let
  efiArch = pkgs.stdenv.hostPlatform.efiArch;
in
{

  imports = [
    (modulesPath + "/image/repart.nix")
  ];

  image.repart.partitions = {
    "00-esp" = {
      contents = {
        "/EFI/BOOT/BOOT${lib.toUpper efiArch}.EFI".source =
          "${pkgs.systemd}/lib/systemd/boot/efi/systemd-boot${efiArch}.efi";

        "/loader/entries/nixos.conf".source = pkgs.writeText "nixos.conf" ''
          title NixOS
          linux /EFI/nixos/kernel.efi
          initrd /EFI/nixos/initrd.efi
          options init=${config.system.build.toplevel}/init ${toString config.boot.kernelParams}
        '';

        "/EFI/nixos/kernel.efi".source =
          "${config.boot.kernelPackages.kernel}/${config.system.boot.loader.kernelFile}";

        "/EFI/nixos/initrd.efi".source =
          "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
      };
      repartConfig = {
        Type = "esp";
        Format = "vfat";
        SizeMinBytes = "1G";
      };
    };
    "01-root" = {
      repartConfig = {
        Type = "root";
        Label = "nixos";
        Format = "ext4";
        Minimize = "guess";
        AutoResize = "yes";
      };
    };
  };

  systemd.repart.partitions = {
    "01-root" = {
      Type = "root";
      AutoResize = "yes";
    };
  };

  fileSystems = {
    "/boot" = {
      device = "/dev/disk/by-partlabel/ESP";
      fsType = "vfat";
    };
    "/" = {
      device = "/dev/disk/by-partlabel/nixos";
      fsType = "ext4";
      autoResize = true;
    };
  };

  boot.loader = {
    timeout = 1;
    systemd-boot.enable = true;
  };

  # Fetch from DHCP
  networking.hostName = lib.mkDefault "";


}

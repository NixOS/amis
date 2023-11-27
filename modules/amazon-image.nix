{ config, modulesPath, lib, pkgs, ... }:
let
  efiArch = pkgs.stdenv.hostPlatform.efiArch;
in
{

  imports = [
    (modulesPath + "/image/repart.nix")
    ./amazon-profile.nix
  ];


  system.build.imageInfo = pkgs.writers.writeJSON "image-info.json" {
    label = config.system.nixos.label;
    system = pkgs.stdenv.hostPlatform.system;
    format = "raw";
    file = "${config.system.build.image}/image.raw";
    boot_mode = "uefi";
  };

  image.repart.name = "${config.system.nixos.distroId}-${config.system.nixos.label}-${pkgs.stdenv.hostPlatform.system}";
  image.repart.partitions = {
    "00-esp" = {
      contents = {
        "/EFI/systemd/systemd-boot${efiArch}.efi".source =
          "${pkgs.systemd}/lib/systemd/boot/efi/systemd-boot${efiArch}.efi";
        "/EFI/BOOT/BOOT${lib.toUpper efiArch}.EFI".source =
          "${pkgs.systemd}/lib/systemd/boot/efi/systemd-boot${efiArch}.efi";

        # TODO: nixos-generation-1.conf
        "/loader/entries/nixos.conf".source = pkgs.writeText "nixos.conf" ''
          title NixOS
          linux /EFI/nixos/kernel.efi
          initrd /EFI/nixos/initrd.efi
          options init=${config.system.build.toplevel}/init ${toString config.boot.kernelParams}
        '';

        "/EFI/nixos/kernel.efi".source = "${config.system.build.kernel}/${config.system.boot.loader.kernelFile}";
        # "${config.boot.kernelPackages.kernel}/${config.system.boot.loader.kernelFile}";

        "/EFI/nixos/initrd.efi".source = "${config.system.build.toplevel}/initrd";
        # "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
      };
      repartConfig = {
        Type = "esp";
        Format = "vfat";
        SizeMinBytes = "1G";
      };
    };
    "01-root" = {
      storePaths = [ config.system.build.toplevel ];
      repartConfig = {
        Type = "root";
        Label = "nixos";
        Format = "ext4";
        Minimize = "guess";
      };
    };
  };

  systemd.repart.enable = true;
  systemd.repart.partitions = {
    "01-root" = { Type = "root"; };
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


}

{
  config,
  lib,
  pkgs,
  modulesPath,
  ...
}:
let
  cfg = config.amazon.ami;
in
{
  imports = [
    "${modulesPath}/image/repart.nix"
    "${modulesPath}/virtualisation/amazon-image.nix"
  ];

  options.amazon.ami = {
    enable = lib.mkEnableOption "Amazon AMI generation using systemd-repart";

    name = lib.mkOption {
      type = lib.types.str;
      default = "nixos-${config.system.nixos.label}-${pkgs.stdenv.hostPlatform.system}";
      description = "The name of the AMI.";
    };

    description = lib.mkOption {
      type = lib.types.str;
      default = "NixOS ${config.system.nixos.label} ${pkgs.stdenv.hostPlatform.system}";
      description = "The description of the AMI.";
    };

    tpmSupport = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable TPM 2.0 support for UEFI x86_64 images.";
    };

    enaSupport = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable ENA support.";
    };

    imdsSupport = lib.mkOption {
      type = lib.types.enum [ "v2.0" "v1.0" ];
      default = "v2.0";
      description = "IMDS version support.";
    };

    public = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Whether to make the AMI public.";
    };

    attestation = {
      enable = lib.mkEnableOption "NitroTPM Attestation support";
    };
  };

  config = lib.mkIf cfg.enable {
    # drop BIOS support and only build UEFI images
    amazonImage.format = "raw";
    
    boot.loader.grub.enable = false;
    boot.loader.systemd-boot.enable = true;
    boot.loader.efi.canTouchEfiVariables = true;

    # systemd-repart for image generation
    image.repart = {
      enable = true;
      name = cfg.name;
      partitions = {
        "esp" = {
          repartConfig = {
            Type = "esp";
            Format = "vfat";
            SizeMinBytes = "128M";
          };
        };
        "root" = {
          repartConfig = {
            Type = "root";
            Format = "ext4";
            Minimize = "best";
          };
        };
      };
    };

    # EC2 metadata and instance attestation bits
    boot.initrd.systemd.enable = true;
    
    environment.systemPackages = lib.optionals cfg.attestation.enable [
      pkgs.nitrotpm-tools
      pkgs.tpm2-tools
    ];

    system.build.ami-info = pkgs.writeText "ami-info.json" (builtins.toJSON {
      name = cfg.name;
      description = cfg.description;
      tpmSupport = cfg.tpmSupport;
      enaSupport = cfg.enaSupport;
      imdsSupport = cfg.imdsSupport;
      public = cfg.public;
      architecture = if pkgs.stdenv.hostPlatform.isAarch64 then "arm64" else "x86_64";
      boot_mode = "uefi";
    });

    system.build.amazon-image = pkgs.stdenv.mkDerivation {
      name = "amazon-image-${cfg.name}";
      
      nativeBuildInputs = [ pkgs.nitrotpm-tools ];
      
      buildCommand = ''
        mkdir -p $out
        IMAGE=$(ls ${config.system.build.image}/*.raw)
        ln -s $IMAGE $out/image.raw
        ln -s ${config.system.build.ami-info} $out/ami-info.json
        
        ${lib.optionalString cfg.attestation.enable ''
          echo "computing NitroTPM PCRs..."
          nitro-tpm-pcr-compute --image $IMAGE > $out/tpm_pcr.json
        ''}
      '';
    };
  };
}

{
  config,
  pkgs,
  lib,
  selfPackages,
  ...
}:
let
  json = pkgs.formats.json { };
  cfg = config.ec2.imds;
in

{
  options.ec2.imds = {
    settings = lib.mkOption {
      type = lib.types.submodule {
        freeformType = json.type;
        options = {
          server.port = lib.mkOption {
            type = lib.types.str;
            default = "80";
          };
          server.hostname = lib.mkOption {
            type = lib.types.str;
            default = "169.254.169.254";
          };
        };
      };
      default = { };
    };
  };
  config = {
    networking.interfaces.lo.ipv4.addresses = [
      {
        address = "169.254.169.254";
        prefixLength = 32;
      }
    ];

    systemd.services.imds = {
      description = "Mock Instance Metadata Service";
      wantedBy = [ "multi-user.target" ];
      serviceConfig.ExecStart = "${lib.getExe pkgs.amazon-ec2-metadata-mock} --config-file ${json.generate "config.json" cfg.settings}";
    };
  };
}

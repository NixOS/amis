{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=nixos-24.11";
    nixos_2411.url = "github:NixOS/nixpkgs?ref=nixos-24.11";
    nixos_unstable.url = "github:NixOS/nixpkgs?ref=nixos-unstable";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      treefmt-nix,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      inherit (lib) genAttrs mapAttrs;
      supportedSystems = [
        "aarch64-linux"
        "x86_64-linux"
        "aarch64-darwin"
      ];
      eachSystem = f: genAttrs supportedSystems (system: f nixpkgs.legacyPackages.${system});
      treefmtEval = eachSystem (
        pkgs:
        treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs.black.enable = true;
          programs.nixfmt.enable = true;
          programs.actionlint.enable = true;
          programs.yamlfmt.enable = false; # check and format dont agree about comments
          programs.shellcheck.enable = true;
        }
      );
    in
    {
      packages = genAttrs supportedSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          upload-ami = pkgs.python3Packages.callPackage ./upload-ami { };
        }
      );
      apps = genAttrs supportedSystems (
        system:
        let
          upload-ami = self.packages.${system}.upload-ami;
          mkApp = name: _: {
            type = "app";
            program = "${upload-ami}/bin/${name}";
          };
        in
        mapAttrs mkApp self.packages.${system}.upload-ami.passthru.pyproject.project.scripts
      );

      formatter = eachSystem (pkgs: treefmtEval.${pkgs.system}.config.build.wrapper);

      checks = genAttrs supportedSystems (system: {
        inherit (self.packages.${system}) upload-ami;
        formatting = treefmtEval.${system}.config.build.check self;
      });

      devShells = genAttrs supportedSystems (system: {
        default = self.packages.${system}.upload-ami;
      });

      hydraJobs = genAttrs [ "nixos_2411" "nixos_unstable" ] (
        release:
        let
          nixpkgs = inputs.${release};
        in
        {
          amazonImage = genAttrs [ "aarch64-linux" "x86_64-linux" ] (
            system:
            (nixpkgs.lib.nixosSystem {
              modules = [
                "${nixpkgs}/nixos/maintainers/scripts/ec2/amazon-image.nix"
                (
                  { config, ... }:
                  # TODO: add beta to version string for beta releases
                  # TODO: add pre to version string for unstable
                  {
                    system.stateVersion = config.system.nixos.release;
                    virtualisation.diskSize = "auto";
                    nixpkgs.hostPlatform = system;
                  }
                )
              ];
            }).config.system.build.amazonImage
          );
        }
      );
    };
}

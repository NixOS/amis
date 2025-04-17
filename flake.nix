{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=nixos-24.11";

    # NOTE: We use the channel tarballs as they contain a .version and
    # .version-suffix file with the naming convetions we want. The
    # lib.trivial.version for flakes and git repos returns the wrong thing
    nixos_2411 = {
      url = "https://channels.nixos.org/nixos-24.11/nixexprs.tar.xz";
      flake = false;
    };
    nixos_unstable = {
      url = "https://channels.nixos.org/nixos-unstable/nixexprs.tar.xz";
      flake = false;
    };
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
          # NOTE: we can not use nixpkgs.lib.nixosSystem as that uses
          # an extended version of lib that overrides lib.trivial.version
          # with something flake-specific which breaks the naming conventions
          # for images. (e.g.  pre for unstable, beta for 25.05, etc)
          nixosSystem = args: import "${nixpkgs}/nixos/lib/eval-config.nix" ({ system = null; } // args);
        in
        {
          amazonImage = genAttrs [ "aarch64-linux" "x86_64-linux" ] (
            system:
            (nixosSystem {
              modules = [
                # TODO: use @phaer's new images interface
                "${nixpkgs}/nixos/maintainers/scripts/ec2/amazon-image.nix"
                (
                  { config, ... }:
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

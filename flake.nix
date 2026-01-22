{
  description = "Upload AMI";

  inputs = {
    nixpkgs.url = "https://channels.nixos.org/nixpkgs-unstable/nixexprs.tar.xz";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
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
          programs.mypy.enable = true;
          programs.mypy.directories."upload-ami" = {
            extraPythonPackages = self.packages.${pkgs.system}.upload-ami.propagatedBuildInputs;
          };
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
          upload-ami = pkgs.callPackage ./upload-ami { };
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
        mapAttrs mkApp self.packages.${system}.upload-ami.passthru.upload-ami.pyproject.project.scripts
      );

      # NOTE: We don't build the production images with these (yet). We use a hydra job instead0
      nixosConfigurations = genAttrs supportedSystems (
        system:
        nixpkgs.lib.nixosSystem {
          modules = [
            (
              { modulesPath, ... }:
              {
                imports = [ "${modulesPath}/virtualisation/amazon-image.nix" ];
                nixpkgs.hostPlatform = system;
              }
            )
          ];
        }
      );

      formatter = eachSystem (pkgs: treefmtEval.${pkgs.system}.config.build.wrapper);

      checks = genAttrs supportedSystems (system: {
        inherit (self.packages.${system}) upload-ami;
        formatting = treefmtEval.${system}.config.build.check self;
        image = self.nixosConfigurations.${system}.images.amazon;
      });

      devShells = genAttrs supportedSystems (system: {
        default = self.packages.${system}.upload-ami;
      });
    };
}

{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=nixos-24.11";
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
      inherit (lib) genAttrs mapAttrs recursiveUpdate;
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
          programs.actionlint = {
            enable = true;
            # includes = [ ".github/workflows/*.yml" ];
          };
          programs.yamlfmt = {
            # includes = [ ".github/**/*.yml" ];
            enable = true;
          };
        }
      );
    in
    {
      nixosModules = {
        ec2-instance-connect = ./modules/ec2-instance-connect.nix;

        legacyAmazonProfile = nixpkgs + "nixos/modules/virtualisation/amazon-image.nix";
        legacyAmazonImage = nixpkgs + "/nixos/maintainers/scripts/ec2/amazon-image.nix";

        amazonProfile = ./modules/amazon-profile.nix;
        amazonImage = ./modules/amazon-image.nix;

        mock-imds = ./modules/mock-imds.nix;
        version =
          { config, ... }:
          {
            system.stateVersion = config.system.nixos.release;
            # NOTE: This will cause an image to be built per commit.
            # system.nixos.versionSuffix = lib.mkForce
            #  ".${lib.substring 0 8 (nixpkgs.lastModifiedDate or nixpkgs.lastModified or "19700101")}.${nixpkgs.shortRev}.${lib.substring 0 8 (self.lastModifiedDate or self.lastModified or "19700101")}.${self.shortRev or "dirty"}";
          };
      };

      packages =
        recursiveUpdate
          (genAttrs supportedSystems (
            system:
            let
              pkgs = nixpkgs.legacyPackages.${system};
            in
            {
              upload-ami = pkgs.python3Packages.callPackage ./upload-ami { };
              amazon-ec2-metadata-mock = pkgs.buildGoModule rec {
                pname = "amazon-ec2-metadata-mock";
                version = "1.11.2";
                doCheck = false; # check is flakey
                src = pkgs.fetchFromGitHub {
                  owner = "aws";
                  repo = "amazon-ec2-metadata-mock";
                  rev = "v${version}";
                  hash = "sha256-hYyJtkwAzweH8boUY3vrvy6Ug+Ier5f6fvR52R+Di8o=";
                };
                vendorHash = "sha256-T45abGVoiwxAEO60aPH3hUqiH6ON3aRhkrOFcOi+Bm8=";
              };
            }
          ))
          (
            genAttrs [ "aarch64-linux" "x86_64-liux" ] (
              system:
              let
                pkgs = nixpkgs.legacyPackages.${system};
              in
              {
                ec2-instance-connect = pkgs.callPackage ./packages/ec2-instance-connect.nix { };
              }
            )
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

      checks =
        recursiveUpdate
          (genAttrs supportedSystems (system: {
            inherit (self.packages.${system}) upload-ami;
            formatting = treefmtEval.${system}.config.build.check self;
          }))
          (
            lib.genAttrs [ "aarch64-linux" "x86_64-linux" ] (
              system:
              let
                pkgs = nixpkgs.legacyPackages.${system};
                config = {
                  node.pkgs = pkgs;
                  node.specialArgs.selfPackages = self.packages.${system};
                  defaults =
                    { name, ... }:
                    {
                      imports = [
                        self.nixosModules.version
                        self.nixosModules.amazonImage
                        self.nixosModules.mock-imds
                      ];
                      # Needed  because test framework insists on having a hostName
                      networking.hostName = "";
                    };
                };
              in
              {
                resize-partition = lib.nixos.runTest {
                  hostPkgs = pkgs;
                  imports = [
                    config
                    ./tests/resize-partition.nix
                  ];
                };
                ec2-metadata = lib.nixos.runTest {
                  hostPkgs = pkgs;
                  imports = [
                    config
                    ./tests/ec2-metadata.nix
                  ];
                };
              }
            )
          );
      devShells = genAttrs supportedSystems (system: {
        default = self.packages.${system}.upload-ami;
      });
    };
}

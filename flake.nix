{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = { self, nixpkgs, ... }:
    let inherit (nixpkgs) lib; in

    {
      nixosModules = {
        ec2-instance-connect = ./modules/ec2-instance-connect.nix;

        legacyAmazonProfile = nixpkgs + "nixos/modules/virtualisation/amazon-image.nix";
        legacyAmazonImage = nixpkgs + "/nixos/maintainers/scripts/ec2/amazon-image.nix";

        amazonProfile = ./modules/amazon-profile.nix;
        amazonImage = ./modules/amazon-image.nix;

        mock-imds = ./modules/mock-imds.nix;
      };

      lib.supportedSystems = [ "aarch64-linux" "x86_64-linux" "aarch64-darwin" ];

      packages = lib.genAttrs self.lib.supportedSystems (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          ec2-instance-connect = pkgs.callPackage ./packages/ec2-instance-connect.nix { };
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
          upload-ami = pkgs.python3Packages.callPackage ./upload-ami { };

          amazonImage = (nixpkgs.lib.nixosSystem {
            specialArgs.selfPackages = self.packages.${system};
            pkgs = nixpkgs.legacyPackages.${system};
            modules = [
              self.nixosModules.ec2-instance-connect
              self.nixosModules.amazonImage
            ];
          }).config.system.build.amazonImage;
          legacyAmazonImage = (lib.nixosSystem {
            specialArgs.selfPackages = self.packages.${system};
            pkgs = nixpkgs.legacyPackages.${system};
            modules = [
              self.nixosModules.legacyAmazonImage
              {
                ec2.efi = true;
                # amazonImage.sizeMB = "auto";
                amazonImage.sizeMB = "auto";
                amazonImage.format = "raw"; # coldsnap requires raw
              }
            ];
          }).config.system.build.amazonImage;

        });

      apps = lib.genAttrs self.lib.supportedSystems (system:
        let
          upload-ami = self.packages.${system}.upload-ami;
          mkApp = name: _: { type = "app"; program = "${upload-ami}/bin/${name}"; };
        in
          lib.mapAttrs mkApp self.packages.${system}.upload-ami.passthru.pyproject.project.scripts
        );


      # TODO: unfortunately I don't have access to a aarch64-linux hardware with virtualisation support
      checks = lib.genAttrs [ "x86_64-linux" ] (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          config = {
            node.pkgs = pkgs;
            node.specialArgs.selfPackages = self.packages.${system};
            defaults = { name, ... }: {
              imports = [
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
            imports = [ config ./tests/resize-partition.nix ];
          };
          ec2-metadata = lib.nixos.runTest {
            hostPkgs = pkgs;
            imports = [ config ./tests/ec2-metadata.nix ];
          };
        });

      devShells = lib.genAttrs [ "x86_64-linux" "aarch64-darwin" ] (system: {
        default = let pkgs = nixpkgs.legacyPackages.${system}; in pkgs.mkShell {
          nativeBuildInputs = [
            pkgs.awscli2
            pkgs.opentofu
          ];
        };
      });
    };
}

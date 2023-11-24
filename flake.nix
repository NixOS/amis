{
  description = "A very basic flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }:
    let inherit (nixpkgs) lib; in

    {
      nixosModules.amazonImage = ./modules/amazon-image.nix;


      packages = lib.genAttrs self.lib.supportedSystems (system: {
        legacyAmazonImage = (lib.nixosSystem {
          pkgs = nixpkgs.legacyPackages.${system};
          inherit system;
          modules = [ (nixpkgs + "/nixos/maintainers/scripts/ec2/amazon-image.nix") ];
        }).config.system.build.amazonImage;
      });

      # systems that amazon supports
      lib.supportedSystems = [ "x86_64-linux" "aarch64-linux" ];

      nixosConfigurations = lib.genAttrs self.lib.supportedSystems
        (system: lib.nixosSystem {
          pkgs = nixpkgs.legacyPackages.${system};
          inherit system;
          modules = [ self.nixosModules.amazonImage ];
        });

      checks = lib.genAttrs self.lib.supportedSystems (system: {
        resizePartition = nixpkgs.legacyPackages.${system}.nixosTest ./tests/resize-partition.nix;
      });

      devShells = lib.genAttrs self.lib.supportedSystems (system: {
        default = let pkgs = nixpkgs.legacyPackages.${system}; in pkgs.mkShell {
          nativeBuildInputs = [
            pkgs.awscli2 pkgs.opentofu
            (pkgs.python3.withPackages (p: [p.boto3 p.botocore]))
          ];
        };
      });

    };
}

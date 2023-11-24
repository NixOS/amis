{
  description = "A very basic flake";

  outputs = { self, nixpkgs }:
    let inherit (nixpkgs) lib; in

    {
      nixosModules.amazonImage = ./modules/amazon-image.nix;

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

    };
}

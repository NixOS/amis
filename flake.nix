{
  description = "A very basic flake";

  outputs = { self, nixpkgs }: {
    nixosModules.amazon-image = ./modules/amazon-image.nix;

    # systems that amazon supports
    lib.supportedSystems = [ "x86_64-linux" "aarch64-linux" ];

    nixosConfigurations = nixpkgs.lib.genAttrs self.lib.supportedSystems
      (system: nixpkgs.lib.nixosSystem {
        pkgs = nixpkgs.legacyPackages.${system};
        inherit system;
        modules = [ self.nixosModules.amazon-image ];
      });
  };
}

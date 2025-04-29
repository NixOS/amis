{
  inputs = {
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
  };

  outputs =
    inputs:
    let
      lib = import "${inputs.nixos_unstable}/lib";
    in
    {

      hydraJobs = lib.genAttrs [ "nixos_2411" "nixos_unstable" ] (
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
          amazonImage = lib.genAttrs [ "aarch64-linux" "x86_64-linux" ] (
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

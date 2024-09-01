# NixOS AMIs

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/arianvp/amis/badge)](https://securityscorecards.dev/viewer/?uri=github.com/arianvp/amis)

[Join our Matrix Channel!](https://matrix.to/#/#aws:nixos.org)

Github Action that regularly uploads AMIs for release channels

> [!NOTE]
> The files in [./modules](./modules) are **NOT** being used yet and we are not **building** images from this repository yet.
> Instead we are uploading the AMIs from this Hydra job:  https://hydra.nixos.org/job/nixos/release-23.11/nixos.amazonImage.x86_64-linux

## Can I use this to upload custom AMIs?

Yes! for example with a config like this:

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs?ref=nixpkgs-unstable";
  outputs = { nixpkgs, ... }: {
    nixosConfigurations.my-system = nixpkgs.nixosSystem {
      system = "aarch64-linux";
      modules = [
        "${nixpkgs}/nixos/maintainers/scripts/ec2/amazon-image.nix"
        { services.ngninx.enable = true; }
      ];
    };
  }
}
```

you can upload it to your account like this:

```
nix run github:NixOS/amis#upload-ami -- --s3-bucket my-bucket --image-info $(nix build .#nixosConfigurations.my-system.config.system.build.amazonImage)
```

## Setting up account

Some steps need to be done manually to set up the account.  This is a one time
process. These are hard to automate with Terraform.

First opt in to all regions:

```bash
nix run .#enable-regions
```

You might get rate-limited so need to wait and rerun until all finish:
```
botocore.errorfactory.TooManyRequestsException: An error occurred (TooManyRequestsException) when calling the EnableRegion operation (reached max retries: 4): This request has exceeded the quota for 'Number of concurrent region-opt requests for an account'. Consider retrying the operation later once some requests have been completed.
```

Now wait until all regions are enabled. You can use:
```
aws account list-regions --region-opt-status-contains ENABLING
```

Then request a quota increase for the number of AMIs you want to publish.
This will create support tickets in all regions.  You can check the status
of the tickets in the AWS console. It might take a few days for the tickets
to be resolved.

```bash
nix run .#request-public-ami-quota-increase -- --desired-value 1000
```

Finally enable public AMIs:

```bash
nix run .#disable-image-block-public-access
```

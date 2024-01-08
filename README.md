# NixOS AMIs

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/arianvp/amis/badge)](https://securityscorecards.dev/viewer/?uri=github.com/arianvp/amis)

Temporary home for the soon to be official NixOS AMIs

## Setting up account

Some steps need to be done manually to set up the account.  This is a one time
process. These are hard to automate with Terraform.

First opt in to all regions:

```bash
nix run .#enable-regions
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
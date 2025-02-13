{ buildGoModule, fetchFromGitHub }:
buildGoModule (finalAttrs: {
  pname = "amazon-ec2-metadata-mock";
  version = "1.11.2";
  doCheck = false; # check is flakey
  src = fetchFromGitHub {
    owner = "aws";
    repo = "amazon-ec2-metadata-mock";
    rev = "v${finalAttrs}";
    hash = "sha256-hYyJtkwAzweH8boUY3vrvy6Ug+Ier5f6fvR52R+Di8o=";
  };
  vendorHash = "sha256-T45abGVoiwxAEO60aPH3hUqiH6ON3aRhkrOFcOi+Bm8=";
})

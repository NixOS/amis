{
  stdenv,
  fetchFromGitHub,
  buildFHSEnv,
  coreutils,
  curl,
  openssh,
  cacert,
  gnugrep,
  util-linux,
  openssl,
  gawk,
  gnused,
}:
# TODO: This currently fails with exit code 1 and no helpful error message.
let
  src = fetchFromGitHub {
    # https://github.com/aws/aws-ec2-instance-connect-config
    owner = "aws";
    repo = "aws-ec2-instance-connect-config";
    rev = "1.1.17";
    hash = "sha256-XXrVcmgsYFOj/1cD45ulFry5gY7XOkyhmDV7yXvgNhI=";
  };
in
buildFHSEnv {
  name = "eic_run_authorized_keys";
  runScript = "${src}/src/bin/eic_run_authorized_keys";
  targetPkgs = (
    p: with p; [
      coreutils
      curl
      openssh
      cacert
      gnugrep
      util-linux
      openssl
      gawk
      gnused
    ]
  );
}

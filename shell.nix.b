# genereate a shell nix with package ruff
{ pkgs ? import <nixpkgs> {} }: 
pkgs.mkShell {
  buildInputs = [
    pkgs.python3
    pkgs.uv
    pkgs.python3Packages.ruff
  ];
  shellHook = ''
    echo "Ruff is ready to use!"
  '';
}

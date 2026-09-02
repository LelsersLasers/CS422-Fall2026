{
  description = "Python env numpy";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          matplotlib
          numpy
        ]);

        runtimeLibs = with pkgs; [
          glib
          libGL
          xorg.libX11
          fontconfig
          freetype
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [ pythonEnv ];

          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath runtimeLibs}:$LD_LIBRARY_PATH"
          '';
        };
      });
}

{ pkgs ? import (fetchTarball "https://github.com/nixos/nixpkgs/archive/nixos-unstable.tar.gz") {
    config.allowUnfree = true;
  }
}:

let
  pythonWithTk = pkgs.python313.withPackages (ps: with ps; [
    pip
    tkinter
    requests
    exceptiongroup
    python-lzo
  ]);

  fhsEnv = pkgs.buildFHSEnv {
    name = "mio-kitchen-fhs";

    targetPkgs = pkgs: (with pkgs; [
      pythonWithTk
      tcl
      tk
      libxcb
      xcb-proto
      libxcursor
      xorg.libX11
      zlib
      stdenv.cc.cc.lib
    ]);

    runScript = pkgs.writeScript "init-fhs.sh" ''
      # Manually configure tkinter on NixOS
      # Refs: https://github.com/NixOS/nixpkgs/issues/238990#issuecomment-2840390721
      export PYTHONPATH="${pythonWithTk}/lib/python3.13/site-packages:$PYTHONPATH"
      export TCL_LIBRARY="${pkgs.tcl}/lib/tcl${pkgs.tcl.version}"
      export TK_LIBRARY="${pkgs.tk}/lib/tk${pkgs.tk.version}"

      # Install under venv
      export VENV_DIR="$PWD/.venv"
      if [ ! -d "$VENV_DIR" ]; then
        python -m venv $VENV_DIR
      fi
      source $VENV_DIR/bin/activate

      # Install deps
      pip install -r requirements.txt

      PYTHON_VERSION=$(python --version)
      echo ""
      echo -e "\033[1;35m[FHS Container]\033[0m Welcome! Running: (\033[1;34m$PYTHON_VERSION\033[0m)"

      export PS1="\n\[\033[1;35m\](FHS:mio-kitchen) \[\033[1;32m\]\u@\h\[\033[00m\]:\[\033[1;34m\]\w\[\033[00m\]\n\$ "

      exec bash --norc
    '';
  };
in
pkgs.stdenv.mkDerivation {
  name = "fhs-shell";
  nativeBuildInputs = [ fhsEnv ];

  shellHook = ''
    exec ${fhsEnv}/bin/mio-kitchen-fhs
  '';
}

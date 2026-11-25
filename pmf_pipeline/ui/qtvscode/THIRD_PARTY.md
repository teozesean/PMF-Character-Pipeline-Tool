# Third-party theme — attribution

The One Dark Pro theme in this folder is third-party work, vendored
into the PMF tool so Maya needs no extra package installed.

## What is here

- `OneDark-Pro.json` — the VS Code theme file, downloaded from
  https://github.com/Binaryify/OneDark-Pro/blob/master/themes/OneDark-Pro.json
  (One Dark Pro by Binaryify, MIT License).
- `onedark_pro.qss` + `svg/*.svg` — generated from that JSON with
  QtVSCodeStyle (`pip install qtvscodestyle`,
  https://github.com/5yutan5/QtVSCodeStyle, MIT License) by running
  `tools/generate_qtvscode_theme.py`. The generator copies the icon
  SVGs QtVSCodeStyle builds in a temp folder into `svg/` and rewrites
  their URLs to the `__QTVSCODE_SVG_DIR__` placeholder, which
  `pmf_pipeline.main` swaps for the real folder at launch.
- QtVSCodeStyle itself incorporates icons from Font Awesome Free
  5.15.4 (SIL OFL 1.1), Material Design Icons (Apache 2.0) and
  vscode-codicons (CC-BY-SA-4.0) — see its NOTICE.md:
  https://github.com/5yutan5/QtVSCodeStyle/blob/main/NOTICE.md

## Licenses

- One Dark Pro theme: MIT — https://github.com/Binaryify/OneDark-Pro/blob/master/LICENSE.md
- QtVSCodeStyle: MIT — https://github.com/5yutan5/QtVSCodeStyle/blob/main/LICENSE.txt

## Regenerating / switching theme

    python tools/generate_qtvscode_theme.py            # rebuild One Dark Pro
    python tools/generate_qtvscode_theme.py dark_vs    # bake a built-in theme instead

See `QT_STYLESHEET_SETUP.md` in the project root for the full walkthrough.

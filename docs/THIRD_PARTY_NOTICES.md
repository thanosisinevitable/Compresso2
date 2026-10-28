# Third-party components

This source project includes the user's original icons. It does not establish new licensing rights to those assets or the original application.

The app uses Electron, React, Vite, Framer Motion, Recharts, Lucide, FastAPI, Uvicorn, Pillow, ImageHash, NumPy, SciPy, scikit-image and ReportLab. The development/build tools include Electron Builder, PyInstaller, Playwright and pytest. Refer to each installed package's license and notices for the exact terms of the version in use.

The Mac packaging script copies Ghostscript and recursively referenced native libraries from the local Homebrew installation. It preserves Ghostscript resources and available Homebrew LICENSE/COPYING files and writes a library manifest into the bundle. Review that manifest and each dependency's notices before distributing builds.

Ghostscript is provided by Artifex under AGPL or commercial licensing. The packaging automation is not a commercial redistribution license and does not determine which licensing option applies to your project. Consult the official licensing terms when distributing a finished app: https://www.ghostscript.com/licensing/index.html

Default app metadata marks the project UNLICENSED; choose an appropriate project license before publishing its source or distributing it publicly. No claim of notarization, Apple endorsement or commercial licensing is made.

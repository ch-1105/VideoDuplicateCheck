# GitHub Upload Checklist

## Before first push

- Confirm project name and visibility (public/private)
- Confirm `README.md` is up to date
- Confirm `.gitignore` excludes local artifacts
- Run local verification:
  - `.venv\\Scripts\\python.exe -m pytest`
  - `.venv\\Scripts\\python.exe -m ruff check src tests`

## Optional release artifacts

- Build onedir package: `scripts\\build_onedir.bat`
- Build onefile package: `scripts\\build_onefile.bat`
- Attach generated executable(s) to GitHub Release (do not commit large binaries into git history)

## Recommended repository sections

- Description: Duplicate and near-duplicate video finder for Windows
- Topics: `python`, `pyside6`, `opencv`, `video`, `desktop-app`
- License: choose one before open-source release (MIT is common)

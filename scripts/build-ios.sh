#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then echo "Esta compilación necesita macOS y Xcode." >&2; exit 1; fi
command -v xcodegen >/dev/null || { echo "Instala XcodeGen: brew install xcodegen" >&2; exit 1; }
xcodebuild -version
cd "$ROOT/ios"
xcodegen generate --spec project.yml
xcodebuild -project Vitra.xcodeproj -scheme Vitra -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath "$ROOT/build/ios" CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
APP="$ROOT/build/ios/Build/Products/Release-iphoneos/Vitra.app"
test -d "$APP"
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/vitra-ipa.XXXXXX")"
trap 'rm -rf -- "$STAGING"' EXIT
mkdir -p "$STAGING/Payload" "$ROOT/dist"
cp -R "$APP" "$STAGING/Payload/Vitra.app"
(cd "$STAGING" && /usr/bin/zip -qr "$ROOT/dist/Vitra-unsigned.ipa" Payload)
(cd "$ROOT/dist" && shasum -a 256 Vitra-unsigned.ipa > Vitra-unsigned.ipa.sha256)
echo "Creada: dist/Vitra-unsigned.ipa (sin firma; requiere firma para instalar)."

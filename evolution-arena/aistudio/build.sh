#!/usr/bin/env sh
# Regenerates aistudio/index.html from ../index.html (adds the @google/genai import map
# and the index.tsx bridge) and packs evolution-arena-aistudio.zip for upload to AI Studio.
set -e
cd "$(dirname "$0")"
awk '!done && /<\/head>/ { done = 1; print "<script type=\"importmap\">{\"imports\":{\"@google/genai\":\"https://esm.sh/@google/genai@^1.39.0\"}}</script>"; print "<script type=\"module\" src=\"/index.tsx\"></script>" } { print }' ../index.html > index.html
rm -rf seeds && cp -r ../seeds seeds
rm -f evolution-arena-aistudio.zip
zip -q evolution-arena-aistudio.zip index.html index.tsx metadata.json package.json vite.config.ts tsconfig.json README.md seeds/peptides.html
echo "Built aistudio/index.html and aistudio/evolution-arena-aistudio.zip"

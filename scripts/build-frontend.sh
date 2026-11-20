#!/usr/bin/env sh
# Recompile l'interface (nécessite Node 18+). La version compilée est déjà livrée dans backend/app/static.
cd "$(dirname "$0")/../frontend" && npm ci && npm run build

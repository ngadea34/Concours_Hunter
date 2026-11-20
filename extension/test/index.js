// Point d'entree pour `node --test extension/test/` (Node >= 22 traite le dossier comme un module).
Promise.all([import('./fill.test.mjs'), import('./e2e.mjs')]);

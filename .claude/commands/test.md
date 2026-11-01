---
description: Génère les cas de test du code ciblé, puis les exécute
argument-hint: [fichier, fonction ou fonctionnalité à tester]
---
Génère les cas de test de : $ARGUMENTS (si vide, des fichiers modifiés selon `git diff`).

Procédure :
1. Lis le code ciblé et les tests existants proches pour imiter leurs conventions (backend : pytest dans backend/tests avec conftest.py, helpers.py et SQLite en mémoire ; frontend : vitest dans src/**/__tests__).
2. Couvre : cas nominaux, cas limites (vide, zéro, négatif, très grand, valeurs aux bornes), erreurs et entrées invalides, régressions plausibles, déterminisme.
3. Pour la géométrie, le nesting et les exports, compare à des valeurs calculées de façon indépendante (formules fermées : aire d'un cercle, dimensions d'un rectangle, distances) avec une tolérance explicite inférieure à 0,1 mm, jamais à un instantané de la sortie actuelle.
4. Écris des tests qui échoueraient si le code était faux ; pas de tests qui valident seulement ce que le code fait déjà.
5. Exécute la suite concernée (`pytest` dans backend/, `npm test` dans frontend/). Si un test échoue, dis-moi si le bug est dans le code ou dans le test avant de corriger.
6. Résume : tests ajoutés, ce qu'ils couvrent, résultat de l'exécution.

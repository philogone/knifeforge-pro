---
description: Crée la documentation technique d'un module, fichier ou fonctionnalité
argument-hint: [fichier, dossier ou fonctionnalité à documenter]
---
Rédige la documentation technique de : $ARGUMENTS (si vide, des changements en cours : `git diff` et `git status`).

Procédure :
1. Lis le code réel concerné (jamais de documentation écrite de mémoire) ainsi que README.md et HANDOVER.md pour respecter leur structure et leur ton.
2. Documente : rôle et périmètre, architecture et fichiers impliqués, flux de données, API (routes, paramètres, réponses, erreurs), modèle de données, règles métier et unités (mm, y vers le bas), décisions et leur pourquoi, limites connues, comment le tester.
3. Pour tout ce qui touche à la géométrie, au nesting et aux exports, précise la précision garantie (tolérance de courbes 0,01 mm, espacement = minimum garanti, arrondis) et ce qui n'est pas garanti.
4. Place le résultat au bon endroit : section existante de README.md / HANDOVER.md, ou nouveau fichier dans docs/ si c'est volumineux. Mets à jour au lieu de dupliquer.
5. Écris en français, de façon concise et vérifiable : chaque affirmation doit correspondre au code. Termine par la liste des fichiers modifiés.

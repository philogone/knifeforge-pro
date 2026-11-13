# Vidéo de présentation

`knifeforge-pro.mp4` : 53 s, 1920 × 1080, 30 images/s, sans son. Huit scènes : ouverture,
dessiner à la cote, outils du coutelier, découper juste, suivre l'atelier, facturer, chez vous,
carton final.

- `motion.html` : l'animation. Ouverte dans un navigateur, elle se joue en boucle.
- `render.mjs` : le rendu image par image et l'assemblage avec ffmpeg
  (`node render.mjs [sortie.mp4] [images/s]`, avec playwright-core, Edge ou Chrome, ffmpeg).
- `assets/` : captures de l'application et polices IBM Plex.

Pour modifier un texte, un chiffre ou un minutage, éditer `motion.html` (table `SCENES` et
fonction `render`), puis relancer le rendu.

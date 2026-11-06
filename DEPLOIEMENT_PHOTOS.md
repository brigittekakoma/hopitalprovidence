# Déploiement des photos d'identité — Hôpital La Providence

## 1. Préparer le stockage persistant Railway

Les photos ne doivent pas être stockées dans le système de fichiers éphémère du conteneur.

1. Dans Railway, ouvrir le service `hopitalprovidence`.
2. Ajouter un Volume au service.
3. Définir le point de montage du volume sur `/data`.
4. Dans les Variables du service, ajouter `UPLOAD_FOLDER=/data/uploads`.
5. Conserver toutes les variables déjà présentes.

Le dossier `/data/uploads` sera créé automatiquement par l'application. Ne pas supprimer ni remplacer le volume lors des déploiements.

## 2. Appliquer la migration PostgreSQL avant le nouveau code

Exécuter le contenu de `migrations_manual/2026_11_person_photos.sql` sur la base PostgreSQL du projet :

```sql
ALTER TABLE patients ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);
ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS photo_path VARCHAR(255);
```

Cette migration ajoute deux colonnes facultatives et conserve les dossiers existants.

## 3. Déployer

Après avoir configuré le volume, la variable et la migration, synchroniser la branche `main` dans GitHub Desktop et déclencher le déploiement Railway.

## 4. Fonctionnement

- Les formulaires patient et personnel acceptent JPG, PNG et WEBP.
- Sur les appareils compatibles, le champ photo peut proposer la caméra.
- Cropper.js permet de déplacer, zoomer et recadrer au format carré (600 × 600).
- Le serveur vérifie le format réel, normalise la photo en JPEG et lui attribue un nom aléatoire.
- Les photos sont servies par une route authentifiée et soumise aux permissions du module.
- Les photos apparaissent sur la fiche patient et les cartes patient/personnel.

## 5. Dépendance de recadrage

L'interface charge Cropper.js depuis cdnjs. Le navigateur doit donc pouvoir accéder à cdnjs.cloudflare.com pour afficher l'outil de recadrage. Si le CDN est bloqué, l'importation reste possible mais le recadrage côté navigateur ne sera pas disponible.

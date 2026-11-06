# Hôpital La Providence — application de gestion hospitalière

Application Flask indépendante, conçue avec une identité visuelle propre à l'Hôpital La Providence. Le dépôt FOBAK sert uniquement de référence fonctionnelle; aucun compte, aucune donnée et aucun code FOBAK ne sont réutilisés comme base opérationnelle.

## Modules présents dans ce prototype
- Authentification et espace de travail
- Dossiers administratifs des patients : création, consultation, modification, suppression sous condition, impression navigateur et export PDF
- Admissions : ouverture de séjour, unités, chambres, lits et sortie administrative
- Facturation : prestations, factures, paiements partiels, séparation CDF/USD et reçu imprimable en formats 58 mm, 80 mm et A4 (impression via navigateur/pilote)
- Pharmacie et stocks : catalogue produits, fournisseurs, réception par lots, péremption, alertes de seuil, délivrance patient, mouvements et journal d'audit
- Laboratoire : catalogue des analyses, demandes rattachées aux patients et séjours, suivi du prélèvement, saisie de résultats, validation par un autre utilisateur, compte rendu imprimable

## Pharmacie : règles du prototype
- Les quantités sont suivies par lot; la quantité disponible d'un article est calculée à partir des quantités restantes des lots actifs.
- Une réception crée un lot et une entrée de stock.
- Une délivrance consomme les lots non périmés en priorité selon FEFO (expiration la plus proche), dans une transaction verrouillée.
- Les lots dont la date de péremption est dépassée ne peuvent pas être délivrés par le formulaire de dispensation.
- Les corrections et retours de stock, inventaires périodiques, gestion multi-magasins et validation pharmaceutique restent à développer.

## Installation locale
1. Python 3.11+ recommandé.
2. `python -m venv .venv` puis activer l'environnement.
3. `pip install -r requirements.txt`.
4. Définir `SECRET_KEY` et `DATABASE_URL` dans l'environnement.
5. Initialiser/appliquer les migrations Flask-Migrate avant le premier lancement.
6. Démarrer avec `flask --app wsgi:app run`.

Les migrations doivent être générées et revues avant d'appliquer ces nouveaux modèles à une base existante. Ne pas utiliser `create_all()` comme stratégie de mise à jour en production.

## Tests et limites
- Compilation syntaxique Python vérifiée dans l'environnement de préparation.
- Tests de contrat statiques pour les routes et règles de facturation/pharmacie ajoutés.
- Tests d'intégration Flask/SQLAlchemy, tests de concurrence PostgreSQL, contrôle des autorisations par rôle, tests matériels d'imprimantes et audit de sécurité restent nécessaires.
- Les données et processus réels de l'établissement doivent être confirmés par la Congrégation avant toute mise en production.
- Aucun déploiement n'a été effectué.


## Laboratoire : circuit du prototype
- Une demande référence un patient, un test du catalogue, une priorité et éventuellement un séjour du même patient.
- Le prélèvement est enregistré avant la saisie du résultat.
- Le résultat reste provisoire jusqu'à sa validation par un utilisateur différent de son auteur.
- Un compte rendu n'est consultable/imprimable qu'après validation; l'impression navigateur permet également l'enregistrement en PDF.
- Les intervalles de référence ne sont pas préremplis arbitrairement : ils doivent être définis et validés par le laboratoire selon les méthodes, unités, équipements, populations et procédures effectivement utilisés.
- Le prototype ne réalise pas d'interprétation médicale automatique et ne remplace pas la validation par un biologiste ou professionnel autorisé.
- Les habilitations fines par fonction, la signature électronique qualifiée, l'interfaçage avec les automates et la gestion des échantillons multi-tubes restent à intégrer et tester.


## Module Consultations médicales (étape de conception)

Le module ajoute les consultations cliniques, les constantes, les observations, le diagnostic, le plan de soins, le suivi et les prescriptions. Les prescriptions sont enregistrées séparément de la délivrance en pharmacie : aucune sortie de stock automatique n'est déclenchée à la seule création d'une ordonnance. Les fiches sont imprimables via le navigateur. Les permissions cliniques fines, les migrations de base de données et les tests d'intégration doivent être finalisés avant une utilisation réelle.

## Accueil, rendez-vous et triage (nouvelle étape)
- Agenda journalier des rendez-vous : patient, date/heure, service et motif; annulation tracée d'un rendez-vous encore planifié.
- Enregistrement des arrivées depuis le dossier patient, avec attribution d'un numéro de file quotidien et priorité normale, urgente ou critique.
- Association facultative à un rendez-vous planifié; le rendez-vous passe à l'état « arrivé » lorsque le patient se présente.
- Triage rattaché à une arrivée : température, pression artérielle, pouls, fréquence respiratoire, saturation, poids, taille, douleur, signes de danger et observations.
- Orientation vers le service et clôture de la visite d'accueil; journal d'audit des opérations.
- Une contrainte d'unicité sur la date et le numéro de file empêche les doublons persistants. Une stratégie de séquencement transactionnel PostgreSQL et un test de charge multi-guichet restent à réaliser avant ouverture réelle.
- Les seuils saisis contrôlent les formats et plages numériques, mais le système ne pose aucun diagnostic et ne décide pas automatiquement du degré d'urgence : la priorisation reste sous responsabilité du personnel soignant.

## Administration des comptes et habilitations

Le projet comprend une gestion des comptes individuels, des rôles, d'un catalogue de permissions et un journal d'audit consultable selon habilitation. Les comptes ne doivent pas être partagés.

Initialisation sur une base neuve ou après migration :

```bash
flask --app wsgi:app init-access
flask --app wsgi:app create-admin
```

Le mot de passe administrateur est demandé de manière interactive et n'est pas écrit dans le dépôt. Protéger les sauvegardes et les secrets de déploiement.

Les droits sont vérifiés côté serveur pour les principales familles de routes. Avant mise en production, compléter la revue des autorisations endpoint par endpoint, ajouter des migrations Alembic pour les bases déjà existantes, configurer une politique de rotation/récupération des mots de passe et réaliser les tests d'intégration avec plusieurs profils professionnels.

## Paie, cartes nominatives et carrousel public
- Le module de paie permet de préparer des bulletins par période, avec salaire de base, gains et retenues configurables, devise CDF/USD/EUR, statut brouillon/validé/payé et impression. Aucun taux fiscal, social ou barème salarial légal n'est codé en dur : la direction doit confirmer les rubriques, taux et règles applicables avant usage réel.
- La carte patient est accessible depuis chaque dossier existant. Après création d'un nouveau patient, l'application ouvre directement sa carte imprimable. Les cartes des patients déjà enregistrés sont accessibles dans le registre.
- La carte de service est accessible depuis chaque dossier RH existant. Après création d'un nouveau membre du personnel, l'application ouvre directement sa carte imprimable.
- Le carrousel de la page d'accueil est piloté depuis Administration > Carrousel accueil. Les utilisateurs habilités peuvent ajouter, modifier, activer/désactiver et ordonner les diapositives (titre, texte, image URL et lien du bouton).
- Les nouvelles tables `payroll_components`, `payroll_records`, `payroll_lines` et `home_slides` exigent une migration de base de données avant mise à jour d'une base existante. Ne pas lancer sur une base de production sans sauvegarde et migration validée.
- Les cartes et bulletins présentés sont des documents administratifs imprimables. Leurs modèles, mentions, formats physiques, photo/signature et dispositifs anti-fraude doivent être validés par l'établissement avant impression officielle.


## Circuit dossier patient / nouveau passage (mise à jour)
Le dossier administratif patient reste permanent. Depuis son dossier, l'agent prépare une facture de passage. L'encaissement est enregistré dans la devise de la facture. Le bouton de création de fiche de passage n'apparaît que lorsque le solde est nul; le serveur recontrôle cette condition et empêche la création répétée d'une fiche pour la même facture. Chaque fiche de passage est liée au dossier patient et à sa facture.

**Migration de base obligatoire avant activation sur une base existante :** sauvegarder la base, puis examiner et exécuter `migrations_manual/2026_11_visit_invoice_link.sql` sur PostgreSQL. Cette migration est fournie comme SQL manuel et n'est pas une migration Alembic générée. Tester d'abord sur une copie de la base. Le paiement complet est la règle par défaut de ce circuit; les urgences, exemptions, assurances et prises en charge doivent faire l'objet d'un workflow validé par la direction avant la mise en production.

### Prises en charge et urgences (mise à jour)

- Les factures peuvent recevoir une autorisation documentée de prise en charge (assurance, exemption ou crédit), avec montant, référence, justification, utilisateur validateur et horodatage.
- Une visite non urgente est ouverte lorsque le solde est réglé ou intégralement couvert par des autorisations validées.
- Un passage urgent peut être enregistré sans paiement préalable; l'opération est auditée et la régularisation financière est traitée séparément.
- La permission `billing.authorize_coverage` doit être attribuée uniquement aux profils désignés par la direction.
- Migration PostgreSQL : sauvegarder la base puis exécuter `migrations_manual/2026_11_payment_exceptions.sql`.
- Les catégories et règles de prise en charge sont configurables et doivent être confirmées par l'établissement; le module ne remplace pas les procédures médicales de triage.


## Sécurité, confidentialité et sauvegardes (mise à jour)

### Paramètres obligatoires en production
- Définir `SECRET_KEY` avec une valeur aléatoire forte d'au moins 32 caractères. L'application refuse maintenant de démarrer en mode production si cette clé est absente, trop courte ou égale à la valeur de développement.
- Activer `COOKIE_SECURE=true` uniquement lorsque l'application est servie en HTTPS. Les cookies de session sont HttpOnly, SameSite=Lax et la session authentifiée est limitée à 45 minutes d'inactivité/durée de vie configurée.
- Ne jamais versionner `.env`, les mots de passe, les clés, les exports SQL ou les sauvegardes. Restreindre l'accès système aux sauvegardes.

### Journalisation et confidentialité
Les connexions/déconnexions sont consignées. Les consultations réussies de certaines pages de dossiers patients, consultations, admissions et laboratoire sont également consignées avec l'utilisateur, l'écran, le type d'entité et l'identifiant technique lorsqu'il est disponible. Les données cliniques, noms, motifs et paramètres médicaux ne sont pas copiés dans le détail du journal. Le journal doit être réservé aux personnes possédant `audit.view`.

### Sauvegarder la base
Exécuter depuis un environnement d'administration ayant accès à la base :

```bash
flask --app wsgi:app backup-db --output /chemin-protege/hopital-backup.dump
```

PostgreSQL utilise `pg_dump` au format custom; SQLite utilise sa fonction de sauvegarde cohérente. Pour PostgreSQL, installer les outils client (`pg_dump` et `pg_restore`) sur l'environnement qui exécute la commande. Prévoir une sauvegarde quotidienne chiffrée, une copie hors serveur, une rétention définie par la direction et un contrôle régulier de la réussite. Le chiffrement au repos et le stockage externe sécurisé doivent être configurés au niveau de l'infrastructure.

### Restaurer (opération destructive)
Arrêter les accès applicatifs, vérifier l'intégrité et la date du fichier, puis exécuter :

```bash
flask --app wsgi:app restore-db --input /chemin-protege/hopital-backup.dump --confirm
```

La commande exige de retaper `RESTAURER`. Une restauration PostgreSQL utilise `pg_restore --clean --if-exists`; une restauration SQLite remplace le contenu de la base cible. Toujours faire une sauvegarde de l'état courant avant restauration, tester d'abord sur un environnement isolé, puis vérifier les dossiers, factures, paiements et journaux avant réouverture.

### Limites et contrôles avant ouverture
Cette étape renforce la base technique mais ne constitue pas une certification de conformité. Il reste indispensable de : (1) réaliser une revue exhaustive des droits sur chaque route, (2) mettre en place les migrations de schéma versionnées, (3) tester sauvegarde/restauration sur une copie PostgreSQL, (4) définir les durées légales de conservation et les habilitations avec la direction, (5) réaliser un audit de sécurité indépendant et des tests d'intrusion, (6) activer HTTPS et sauvegardes chiffrées côté hébergeur. La sécurité de la base et des sauvegardes dépend aussi de la configuration réelle de l'hébergement.


## Rendez-vous en ligne
Formulaire public `/demande-rendez-vous`; traitement par l'accueil `/accueil/demandes-rendez-vous`. Appliquer la migration SQL `2026_11_online_appointment_requests.sql` et configurer les variables SMTP `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `MAIL_USE_SSL`. La demande reste en attente jusqu'à validation ; l'e-mail précise le créneau exact. Aucun détail clinique n'est envoyé.
\n\n## Agenda des professionnels\nAgenda quotidien `/consultations/agenda-professionnels`; configuration hebdomadaire `/rh/horaires-consultation`. L'acceptation d'une demande exige un professionnel actif et un horaire valide, refuse les congés approuvés et les chevauchements. Appliquer `migrations_manual/2026_11_professional_agenda.sql`. Les créneaux sont paramétrés par défaut à 30 minutes dans la validation des demandes en ligne.\n\n\n## Créneaux disponibles calculés automatiquement\nDans le traitement des demandes, le choix du professionnel et de la date charge les créneaux libres via `/api/consultation-slots`. La durée provient de l'horaire hebdomadaire du professionnel ; les congés approuvés et rendez-vous planifiés sont exclus. L'acceptation revalide côté serveur le créneau afin de limiter les réservations concurrentes. Endpoint réservé aux utilisateurs connectés disposant des droits d'accueil.\n

## Portail patient personnel (nouveau)

Le portail patient est séparé de l'authentification du personnel. L'accueil peut envoyer une invitation à partir du dossier patient. Le lien d'activation est à usage unique et expire après 24 heures. Le patient définit lui-même un mot de passe (12 caractères minimum) ; aucun mot de passe n'est envoyé par e-mail.

Le patient peut consulter uniquement ses propres rendez-vous et soumettre une demande d'annulation ou de report. Le rendez-vous n'est pas modifié tant qu'un agent d'accueil n'a pas pris de décision. Les décisions sont journalisées et une notification e-mail est tentée. Le portail ne donne pas accès aux résultats médicaux, consultations, ordonnances, factures ou paiements.

### Migration à appliquer

Après sauvegarde de la base, appliquer `migrations_manual/2026_11_patient_portal.sql` sur la base PostgreSQL cible. Les deux nouvelles tables sont `patient_portal_accounts` et `patient_appointment_change_requests`. Ne pas appliquer cette migration à une base de production sans sauvegarde préalable.

### Configuration / contrôles nécessaires avant mise en service

- Vérifier l'identité du patient et son adresse e-mail avec lui avant d'envoyer l'invitation.
- Configurer le SMTP (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `MAIL_USE_SSL`).
- Attribuer l'autorisation `patients.portal_invite` (ou `patients.edit`) aux agents habilités ; attribuer `reception.manage` aux agents qui traitent les demandes.
- Activer HTTPS et `COOKIE_SECURE=true` en production ; protéger les sauvegardes et limiter l'accès à la base.
- Prévoir une procédure d'assistance/réinitialisation du mot de passe avant ouverture générale du portail. Cette version ne contient pas encore de réinitialisation automatique du mot de passe ni de limitation anti-bruteforce dédiée.

### Limites de validation

Le code Python a été compilé syntaxiquement. Les dépendances Flask ne sont pas installées dans l'environnement de génération ; les tests d'intégration, migrations sur PostgreSQL, envoi SMTP et parcours navigateur restent à exécuter dans l'environnement de déploiement. Aucun déploiement n'a été effectué.


## Rappels automatiques de rendez-vous

La commande `flask --app wsgi:app send-appointment-reminders` recherche les rendez-vous planifiés dans les fenêtres J-1 (24 h avant, tolérance ±15 min) et H-2 (2 h avant, tolérance ±15 min). Elle envoie un e-mail administratif sans donnée clinique et journalise chaque tentative. Un rappel déjà envoyé n'est jamais renvoyé ; un échec peut être retenté lors d'une exécution ultérieure. Les rendez-vous sans adresse e-mail sont ignorés. L'adresse du compte portail actif est prioritaire, sinon l'adresse du dossier patient est utilisée.

**Planification recommandée :** exécuter la commande toutes les 15 minutes via le planificateur Railway ou un cron externe, après configuration SMTP. Tester d'abord avec `flask --app wsgi:app send-appointment-reminders --dry-run`. Consulter l'historique via `/accueil/notifications-rendez-vous` avec un compte disposant des droits d'accueil.

Appliquer `migrations_manual/2026_11_appointment_notifications.sql` après sauvegarde de la base. La commande est idempotente pour les rappels envoyés grâce à la contrainte unique (rendez-vous, type). L'envoi dépend de la disponibilité SMTP ; les échecs sont conservés pour diagnostic et nouvelle tentative.

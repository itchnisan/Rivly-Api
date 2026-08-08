# Scénario de test manuel — Swagger UI

Ce document décrit un parcours complet pour tester l'API à la main via Swagger UI (`/docs`).

## 0. Prérequis

```bash
cp .env.example .env
docker compose up -d
source .venv/bin/activate   # ou: python3 -m venv .venv && pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Ouvrir http://localhost:8000/docs

## 1. Créer un compte — `POST /api/v1/auth/register`

"Try it out" avec :

```json
{
  "email": "pecheur@rivly.dev",
  "username": "pecheur1",
  "password": "secret123"
}
```

Résultat attendu : `201`, réponse avec `id`, `email`, `username`, `created_at` (pas de mot de passe dans la réponse).

Rejouer la même requête doit renvoyer `400` (email déjà utilisé).

## 2. S'authentifier via le bouton "Authorize"

En haut de la page Swagger, cliquer sur le cadenas **Authorize**. Une fenêtre OAuth2 s'ouvre avec des champs `username` / `password` :

- `username` : `pecheur@rivly.dev` (c'est l'email)
- `password` : `secret123`

Cliquer sur **Authorize** puis **Close**. Swagger appelle `POST /api/v1/auth/login` en arrière-plan, récupère le token JWT et l'ajoute automatiquement à l'en-tête `Authorization` de toutes les requêtes suivantes (cadenas maintenant fermé sur les endpoints protégés).

Vérification indépendante possible via `POST /api/v1/auth/login` directement : mauvais mot de passe → `401`, email inconnu → `401`.

## 3. Créer un spot — `POST /api/v1/spots`

```json
{
  "name": "Etang du Moulin",
  "description": "Coin tranquille, bordure d'arbres",
  "latitude": 48.85,
  "longitude": 2.35,
  "water_type": "pond"
}
```

Résultat attendu : `201`, avec `id`, `created_by` (= id de l'utilisateur courant), `created_at`.

Sans être authentifié (cadenas ouvert / token retiré), la même requête doit renvoyer `401`.

Noter l'`id` du spot créé (ex. `1`) pour la suite.

## 4. Lister / filtrer les spots — `GET /api/v1/spots`

- Sans paramètres : doit renvoyer tous les spots, y compris celui créé à l'étape 3.
- Avec bbox englobante, ex. `min_lat=48&max_lat=49&min_lon=2&max_lon=3` : le spot doit apparaître.
- Avec bbox ne contenant pas le point, ex. `min_lat=0&max_lat=1&min_lon=0&max_lon=1` : liste vide.

## 5. Consulter / modifier / supprimer un spot

- `GET /api/v1/spots/{id}` avec l'id noté → `200` avec le détail. Avec un id inexistant (ex. `999999`) → `404`.
- `PATCH /api/v1/spots/{id}` avec `{"name": "Etang du Moulin (renommé)"}` → `200`, nom mis à jour.
- Test de permission : créer un **second compte** (étape 1 avec un autre email), l'autoriser (étape 2), puis tenter `PATCH` ou `DELETE` sur le spot du premier utilisateur → `403`.
- `DELETE /api/v1/spots/{id}` par son propriétaire → `204`. Un `GET` suivant sur ce même id → `404`.

Recréer un spot avant de continuer si celui-ci a été supprimé (il est nécessaire pour l'étape 7).

## 6. Espèces — insertion manuelle puis lecture

Il n'y a pas d'endpoint de création pour les espèces (seulement liste + détail, conformément au périmètre du projet). Pour avoir une donnée à consulter, insérer une ligne directement en base :

```bash
docker exec -i rivly-api-db-1 psql -U rivly -d rivly -c \
  "INSERT INTO species (name, common_name, legal_size_cm, open_season_start, open_season_end) \
   VALUES ('Esox lucius', 'Brochet', 60, '2026-05-01', '2027-01-31');"
```

- `GET /api/v1/species` → `200`, la liste contient "Brochet".
- `GET /api/v1/species/{id}` avec l'id retourné → `200`, détail complet.
- `GET /api/v1/species/999999` → `404`.

## 6 bis. Indice de pêchabilité — `GET /api/v1/spots/{id}/fishability`

Avec l'`id` du spot de l'étape 3. L'endpoint est public : il fonctionne cadenas ouvert.

- Sans paramètre → `200`, avec un `score` de 0 à 100, un `rating`, les sept `factors`
  détaillés (la somme des `contribution` fait le score) et les `weather` bruts ayant servi au calcul.
- Avec `at=2026-08-09T05:00:00Z` (une aube proche) → le facteur `time_of_day` doit être au maximum.
  Comparer avec un `at` en milieu d'après-midi : le score doit baisser.
- Avec `at` très éloigné (ex. `2030-01-01T00:00:00Z`) → `422`, hors fenêtre de prévision.
- Avec `species_id` = l'id du brochet inséré à l'étape 6 → les `advisories` mentionnent la taille légale.
  Le brochet étant ouvert du 1er mai au 31 janvier, tester une date hors saison (ex. `at=2026-03-15T10:00:00Z`)
  doit renvoyer un `score` de `0` et un avis de niveau `blocking`.
- Sur un `id` de spot inexistant → `404`.

Le premier appel sur un secteur donné interroge Open-Meteo (~200 ms) ; les suivants sortent du cache pendant une heure.

## 7. Créer une capture — `POST /api/v1/catches`

Avec le token toujours autorisé (étape 2), utiliser l'`id` du spot (étape 3) et de l'espèce (étape 6) :

```json
{
  "spot_id": 1,
  "species_id": 1,
  "weight_g": 2500,
  "length_cm": 58.5,
  "caught_at": "2026-07-28T10:00:00Z",
  "conditions": {
    "weather": "nuageux",
    "water_temp_c": 18,
    "moon_phase": "decroissante"
  },
  "notes": "Belle prise au vif"
}
```

Résultat attendu : `201`, `user_id` = utilisateur courant, `conditions` renvoyé tel quel (JSON libre).

Avec un `species_id` ou `spot_id` inexistant → `500` (contrainte de clé étrangère en base ; aucune validation métier n'est faite dans ce scaffold).

## 8. Lister / modifier / supprimer ses captures

- `GET /api/v1/catches` → liste des captures de l'utilisateur courant uniquement.
- Se ré-authentifier avec le **second compte** (étape 5) et rappeler `GET /api/v1/catches` → liste vide (isolation par utilisateur).
- Revenir au premier compte, `GET /api/v1/catches/{id}` → `200`. Avec l'id d'une capture appartenant à l'autre utilisateur → `404` (pas `403` : on ne révèle pas l'existence de la ressource).
- `PATCH /api/v1/catches/{id}` avec `{"notes": "note modifiee"}` → `200`.
- `DELETE /api/v1/catches/{id}` → `204`, puis `GET` sur le même id → `404`.

## 9. Health check

`GET /health` (hors `/api/v1`) → `200`, `{"status": "ok"}`. Utile pour vérifier que l'API tourne sans passer par Swagger.

---

Pour une vérification automatisée équivalente (hors Swagger), voir `pytest -v` (cf. README, section Tests).

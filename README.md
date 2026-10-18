# 🚄 SNCF HA

Intégration Home Assistant minimale : les prochains trains directs d'un trajet à partir d'une heure donnée,
avec leur statut (à l'heure / retard / **annulé**) et le temps de retard.

## Installation

HACS → Dépôts personnalisés → URL de ce dépôt (catégorie *Intégration*) → installer → redémarrer.
Manuel : copier `custom_components/sncf_ha` dans `config/custom_components/`.

## Configuration

*Paramètres → Appareils et services → Ajouter → SNCF HA*

1. Clé API gratuite : <https://numerique.sncf.com/startup/api/>
2. Saisir une partie du nom des gares de départ et d'arrivée, puis les choisir dans la liste.
3. Choisir l'**heure de début** (ex. `07:00`, heure de Paris) et le **nombre de trains** à afficher (défaut 5).

Un trajet = une entrée. Réglages ultérieurs (*Configurer*) : **intervalle d'actualisation** (3 à 60 min, défaut 5),
heure de début, nombre de trains.

Fonctionnement : le tableau est composé des **N trains à partir de l'heure de début**.

- **Avant l'heure de début** : une mise à jour par heure, avec les N trains à partir de l'heure de début.
- **À partir de l'heure de début** : ces N trains sont actualisés à l'intervalle choisi (retards, annulations).
- **Quand les N trains sont partis** : retour en veille (une mise à jour par heure) ; le tableau affiche les trains
  du lendemain à partir de l'heure de début.

Après un redémarrage de Home Assistant (ou un changement d'options) en cours de journée, le tableau est reconstruit
à partir de l'heure courante : il montre alors les N prochains trains.

## Entités (par trajet)

| Entité | Rôle |
|---|---|
| `sensor.…_trains` | État = nombre de trains. Attribut `trains` : pour chaque train `number`, `direction`, `mode`, `status` (`on_time` / `delayed` / `cancelled`), `scheduled_departure`, `departure`, `delay_minutes`, `arrival_delay_minutes`, `message`. Attributs `cancelled_count` et `delayed_count`. |
| `event.…_annulation` | Un événement `cancelled` quand un train vient d'être annulé (une seule fois par train), avec le détail du train en attributs. |

Pas d'alerte à la première mise à jour après un démarrage. Les retards n'ont pas d'événement : ils sont dans la
liste, à vous de les renvoyer depuis une automatisation.

## Carte « tableau d'affichage »

[`examples/lovelace_card.yaml`](examples/lovelace_card.yaml) : carte Markdown native (aucune ressource à installer).

```
19/10 - 07:55 - n°8501 - ✅ À l'heure
19/10 - 08:03 - n°8503 - ⚠️ Retard +5 min (départ 08:08)
19/10 - 08:27 - n°8505 - ❌ Annulé
```

## Automatisations

[`examples/automations.yaml`](examples/automations.yaml) : notification à chaque train annulé, et notification
des retards en cours à chaque changement de la liste.

## Comment les annulations sont détectées

L'API temps réel ne renvoie généralement pas un train supprimé. Chaque mise à jour fait donc **2 requêtes** :
temps réel (horaires fiables) + horaire théorique (qui liste encore le train avec sa perturbation).
Un train est `cancelled` si une perturbation `NO_SERVICE` active couvre son départ, si une perturbation supprime
la gare de départ ou d'arrivée **de votre trajet**, ou si le trajet est marqué `NO_SERVICE`.

## Quota

Chaque mise à jour = 2 requêtes API. Le rythme rapide ne dure que de l'heure de début jusqu'au départ du dernier train
(ex. 1 h à 5 min = 12 mises à jour) ; le reste du temps : 1 mise à jour par heure, soit ≈ 48 requêtes/jour. Limites : trains directs uniquement, 20 trains maximum.

## Développement

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check . && pytest
```

Logique pure et testée : `parser.py`, `models.py`, `changes.py`, `window.py`.

## Licence

À choisir par l'auteur (ajoutez un fichier `LICENSE`).

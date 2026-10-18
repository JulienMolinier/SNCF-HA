# 🚄 SNCF Departures

Intégration Home Assistant : prochains trains directs entre deux gares, avec **gestion des trains annulés**.

## Installation

HACS → Dépôts personnalisés → URL de ce dépôt (catégorie *Intégration*) → installer → redémarrer.
Manuel : copier `custom_components/sncf_departures` dans `config/custom_components/`.

## Configuration

*Paramètres → Appareils et services → Ajouter → SNCF Departures*

1. Clé API gratuite : <https://www.digital.sncf.com/startup/api> (5 000 requêtes/jour).
2. Saisir une partie du nom des gares de départ et d'arrivée, puis choisir dans la liste.

Un trajet = une entrée de configuration. Ajoutez-en autant que nécessaire.
Options : intervalle de mise à jour (défaut 5 min), nombre de trains (défaut 5).

## Entités (par trajet)

| Entité | Description |
|---|---|
| `sensor.…_prochain_depart` | Heure réelle du prochain train **qui circule** (timestamp). Attributs : détail du train + liste `trains`. |
| `sensor.…_retard_du_prochain_train` | Retard en minutes. |
| `sensor.…_trains_annules` | Nombre de trains annulés dans la fenêtre. Attribut `trains`. |
| `binary_sensor.…_annulation` | `on` si au moins un train est annulé (classe `problem`). |

Chaque train de l'attribut `trains` contient : `number`, `direction`, `mode`, `status`
(`on_time` / `delayed` / `cancelled`), horaires prévus et réels, retards, `message`.

## Trains annulés : fonctionnement

L'API en temps réel ne renvoie généralement pas un train supprimé. Chaque mise à jour fait donc
**2 requêtes** : vue temps réel (horaires fiables) + vue horaire théorique (qui liste encore le train
avec sa perturbation). Un train est `cancelled` si :

1. une perturbation `NO_SERVICE` active/à venir couvre son départ ;
2. une perturbation supprime la gare de départ ou d'arrivée **de votre trajet** (le train roule, pas pour vous) ;
3. le trajet est marqué `NO_SERVICE`.

Les trains annulés sont exclus de « prochain départ », comptés dans « trains annulés » et déclenchent le binary sensor.

Exemple d'automatisation :

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.paris_lyon_annulation
    to: "on"
action:
  - action: notify.mobile_app_phone
    data:
      message: "{{ state_attr('binary_sensor.paris_lyon_annulation', 'trains')[0].message }}"
```

## Limites

- Trains directs uniquement (`max_nb_transfers=0`).
- Quota : 2 requêtes par mise à jour et par trajet (5 min ≈ 576 requêtes/jour/trajet).

## Développement

```bash
pip install -r requirements_test.txt
ruff check . && ruff format --check . && pytest
```

Structure : `api.py` (client), `parser.py` + `models.py` (logique pure, testée), `coordinator.py`,
`config_flow.py` (+ reauth + options), `sensor.py`, `binary_sensor.py`, `entity.py`.

## Licence

À choisir par l'auteur (ajoutez un fichier `LICENSE`).

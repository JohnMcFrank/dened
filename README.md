DENED est une plateforme de pilotage de pods Kubernetes utilisant un sidecar Tor par pod.

L'objectif est de fournir une interface unique permettant :

- de visualiser les pods du cluster
- de visualiser les IP Kubernetes de chaque pod
- de visualiser l'IP Tor visible de chaque pod
- de surveiller les rotations d'identité Tor
- de lancer ou arrêter les traitements
- de surveiller la consommation système
- de consulter les journaux d'activité
- de contrôler le nombre de pods depuis l'interface

# Architecture

Chaque pod DENED contient :

- 1 conteneur DENED
- 1 conteneur Tor

Architecture :

┌───────────────────┐
│ Pod DENED         │
│                   │
│  Application      │
│       │           │
│       ▼           │
│     Tor           │
│       │           │
│       ▼           │
│   Internet        │
└───────────────────┘

Chaque pod possède :

- sa propre IP Kubernetes
- son propre service Tor
- son propre circuit Tor
- sa propre IP de sortie Tor

---

# Accès à l'interface

Après déploiement :

kubectl port-forward svc/dened-service 8080:8080

Interface :

http://127.0.0.1:8080
Interface utilisateur

L'interface est organisée en plusieurs sections :

1. Destination & comportement

Permet de configurer les traitements.

Destination autorisée

URL cible utilisée par le scheduler.

Exemple :

https://check.torproject.org/api/ip
Mode

Trois modes sont disponibles.

Basique

Envoie :

1 requête toutes les X secondes

Utilisation faible.

Rapide

Envoie :

plusieurs requêtes par seconde
pendant une durée définie

Utilisation moyenne.

Extrême contrôlé

Fonctionne :

sans durée limite
jusqu'à arrêt manuel

Utilisation élevée.

Intervalle basique

Définit le délai entre deux requêtes.

Exemple :

5

Signifie :

1 requête toutes les 5 secondes

Plus la valeur est grande :

moins de trafic
moins de consommation

Plus la valeur est petite :

plus de trafic
plus de consommation
Durée rapide

Durée du mode rapide.

Exemple :

60

Signifie :

60 secondes
Pods souhaités

Nombre de pods DENED à exécuter.

Exemple :

3

Résultat :

3 pods
3 conteneurs DENED
3 conteneurs Tor
3 IP Kubernetes
3 IP Tor potentielles
RPS max / pod

RPS :

Requests Per Second

Nombre maximal de requêtes par seconde pour chaque pod.

Exemple :

5

Signifie :

5 requêtes par seconde maximum
par pod

Calcul :

RPS total = Pods × RPS par pod

Exemple :

4 pods × 5 RPS
=
20 RPS maximum
Workers / pod

Nombre de threads internes utilisés par chaque pod.

Plus la valeur augmente :

plus de parallélisme
plus de CPU
plus de mémoire

Plus la valeur diminue :

plus stable
moins rapide

Valeurs recommandées :

RPS 1 à 5
Workers 1 à 4
Méthode

Méthode HTTP utilisée.

GET

Lecture d'une URL.

POST

Envoi de données.

Pour les tests classiques :

GET recommandé
Cartes Pods

Chaque pod possède sa propre carte.

Une carte affiche :

nom du pod
IP Kubernetes
IP Tor visible
état du pod
état Tor
CPU
mémoire
nombre de requêtes
succès
erreurs
Rotation Tor

Chaque pod dispose de son propre circuit Tor.

L'interface affiche :

ancienne IP
nouvelle IP

Lors d'une rotation :

la carte du pod clignote

afin de signaler le changement.

Boutons
Appliquer pods

Modifie le nombre de pods Kubernetes.

Equivalent :

kubectl scale deployment dened --replicas=X
Démarrer sur tous les pods

Démarre le scheduler sur tous les pods.

Arrêter tous les pods

Arrête tous les schedulers.

Rotation Tor globale

Demande une nouvelle identité Tor sur tous les pods.

Actualiser

Recharge immédiatement toutes les données.

Journal des requêtes

Affiche :

heure
pod
IP Kubernetes
URL cible
proxy utilisé
code HTTP
temps de réponse
Informations système

L'interface affiche :

CPU

Utilisation CPU actuelle.

Mémoire utilisée

Mémoire actuellement utilisée.

Mémoire libre

Mémoire encore disponible.

Pods actifs

Nombre de pods actuellement opérationnels.

Commandes utiles

Voir les pods :

kubectl get pods -l app=dened -o wide

Voir les logs DENED :

kubectl logs deployment/dened -c dened --tail=100

Voir les logs Tor :

kubectl logs deployment/dened -c tor --tail=100

Voir les informations cluster :

curl http://127.0.0.1:8080/api/cluster
Réglages recommandés
Test léger
Mode : Basique
Pods : 1
Intervalle : 5
RPS : 1
Workers : 1
Test moyen
Mode : Rapide
Pods : 3
Durée : 60
RPS : 3
Workers : 2
Test intensif
Mode : Extrême contrôlé
Pods : 5+
RPS : 5+
Workers : 4+

Surveiller systématiquement :

CPU
mémoire
stabilité des pods
stabilité Tor
APIs principales

Etat cluster :

GET /api/cluster

Etat local :

GET /api/runtime

Etat Tor :

GET /tor/status

Nouvelle identité Tor :

POST /tor/new-identity

Démarrage :

POST /api/start

Arrêt :

POST /api/stop

Scale :

POST /api/scale

Version : DENED UI V4

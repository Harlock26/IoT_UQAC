# IoT_UQAC

Projet scolaire réalisé en 2026 dans le cadre du cours 8INF924 – Internet des objets de l'UQAC.

## How tu use
Installez les librairies nécessaires au fonctionnement de l'IHM : 
```bash
pip install requirements.txt
```
Ouvrez le projet `ihm/ihm\_iot\_watch/pyproject.toml` sur Qt Creator puis exécutez le.
Renseigner le SSID et le mot de passe de votre réseau wifi dans le fichier `IoT\_sketch/arduino_secrets.h`
Ouvrez le fichier `IoT\_sketch/IoT\_sketch.ino` avec Arduino IDE et téléversez le sur la carte arduino.
Les 2 parties se connectent automatiquement à un broker MQTT de test accessible sur internet et le projet fonctionne.

## Contexte
Réalisation d'un appareil IoT de suivi de l'activité grâce à un capteur de rythme cardiaque et un accéléromètre.
Pour notre projet, nous nous sommes orientés vers le développement d'une montre connectée en intégrant les fonctionnalités suivantes :
- Calcul et affichage du rythme cardiaque
- Synchronisation et affichage de l'heure
- Traitement, stockage et visualisation des données sur un IHM

## Composants utilisés
Référence   | Description                                       | Quantité  |
--- | --- | ---
SEN0203     | Heart rate sensor	                                | 1         |
SEN0224	    | 3-axis IMU                                        | 1         |
MKR1010	    | Arduino MKR1010                                   | 1         |
DFR0464	    | I2C 16x2 Arduino LCD with RGB Backlight Display   | 1         |
DFR0440	    | Vibration Module                                  | 1         |
DFR0029	    | Push Button                                       | 1         |

## Technologies utilisées
- WiFi : Pour connecter la carte Arduino à internet
- MQTT : Protocole applicatif léger développé pour l'IoT
- Broker Mosquitto : Un broker MQTT de test pour gérer le transfert des données MQTT
- pyQt (pySide6) : IHM qui récupère les donées des topics MQTT, les traite, les sauvegarde et les affiche en temps réel

## Répartition des tâches entre l'appareil IoT et l'IHM
La carte Arduino sert à la mesurer des données brutes et afficher des données traitées simples.
L'IHM sert à traiter les données brutes, afficher les données traitées, publier certaines données traitées et sauvegarder les données dans une base de données SQLite.

## Fonctionnement de l'application
À l'initialisation, la carte arduino se connecte au WiFi, puis au broker MQTT (URL hardcoddée dans le code arduino),puis elle s'inscrit aux topics MQTT.
Elle récupère ensuite l'heure pour l'afficher sur l'écran LCD

La carte arduino mesure et envoie les données brut de ses capteurs à l'IHM (flux sanguin et accélération selon 3 axes) à une fréquence de 5Hz.

L'IHM récupère les données postées par la carte arduino, les traite pour calculer le rythme cardiaque, la vitesse et la position.
Il affiche ces données, les sauvegardes et publie le rythme cardiaque pour que la carte arduino l'affiche.

## Architecture du dépot Github

### Branche main

Le dossier `IoT\_sketch` contient le fichier `IoT\_sketch.ino` à uploader sur la carte Arduino
Le dossier ihm contient le code de l'IHM développé avec QtCreator et la base de données SQLite
Les dossiers `accelerometer\_data` et `heartrate\_data` contiennent des enregistrements de données, des données synthétiques et des scripts de traitement des données. Ces scripts sont déceonnectés du reste de l'architecture et servent de base à certaines classes de l'IHM.

### Branche Dh

La branche dh contient le début de l'implémentation d'un échange de secret avec Elliptic-curve Diffie–Hellman (ECDH).
Elle est composée d'un submodule d'une librairie `ecdh.c` décrivant un échange de secret via ECDH.
La librairie `ecdh.c` est implémentée dans l'IHM et le code de la carte arduino mais ce dernier se bloque après l'échange de secret

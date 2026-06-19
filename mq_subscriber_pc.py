# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "paho-mqtt>=2.1.0",
# ]
# ///
from paho.mqtt import client as mqtt
import json
import csv
import os
from datetime import datetime

BROKER = "test.mosquitto.org"
PORT = 1883
TOPICS = [
   "acceleration",
   "heartrate"
]

CSV_FILE = "accelerometer_data/acceleration_data.csv"

# Crée le fichier CSV avec l'en-tête s'il n'existe pas encore
if not os.path.isfile(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x", "y", "z"])

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT broker.")
        for topic in TOPICS:
            client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")
    else:
        print(f"Connection failed with reason code {reason_code}")

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    print("Received data:", data, "from topic ", msg.topic)

    if msg.topic == "acceleration":
        # data est attendu sous la forme [x, y, z]
        if isinstance(data, list) and len(data) == 3:
            timestamp = datetime.now().isoformat()
            x, y, z = data
            with open(CSV_FILE, mode="a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, x, y, z])
        else:
            print("Format de données d'accélération inattendu :", data)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, keepalive=60)

print("MQTT subscriber running. Press Ctrl+C to exit.")
client.loop_forever()

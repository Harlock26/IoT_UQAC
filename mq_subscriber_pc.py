from paho.mqtt import client as mqtt
import json

BROKER = "test.mosquitto.org"
PORT = 1883
TOPICS = [
   "acceleration",
   "heartrate"
]

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
    print("Received data:", data)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, keepalive=60)

print("MQTT subscriber running. Press Ctrl+C to exit.")
client.loop_forever()
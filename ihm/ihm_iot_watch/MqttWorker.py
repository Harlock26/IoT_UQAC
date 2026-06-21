from PySide6.QtCore import QThread, Signal
import paho.mqtt.client as mqtt

class MqttWorker(QThread):
    """Tourne dans un thread séparé, écoute le broker MQTT,
    et émet un signal Qt à chaque message reçu (thread-safe)."""

    message_received = Signal(str, bytes)  # topic, payload brut
    connected = Signal()
    disconnected = Signal()

    def __init__(self, broker_host, port=1883, topics=None, parent=None):
        super().__init__(parent)
        self.broker_host = "test.mosquitto.org"
        self.port = 1883
        self.topics = ["acceleration","heartrate"]

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self._is_connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._is_connected = True
            for topic in self.topics:
                client.subscribe(topic)
            self.connected.emit()
        else:
            print(f"Échec de connexion MQTT, code retour : {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._is_connected = False
        self.disconnected.emit()

    def _on_message(self, client, userdata, msg):
        # On émet juste le brut ici, le parsing se fait côté UI
        self.message_received.emit(msg.topic, msg.payload)

    def run(self):
        """Appelé automatiquement par .start() — tourne dans le thread."""
        self.client.connect(self.broker_host, self.port)
        self.client.loop_forever()

    def publish(self, topic, payload, qos=0, retain=False):
        """Publie un message sur le broker MQTT.

        paho-mqtt gère le thread-safety en interne pour client.publish(),
        donc cette méthode peut être appelée directement depuis le thread UI
        (pas besoin de signal/slot pour ce sens-là)."""
        if not self._is_connected:
            print("Publication ignorée : MQTT non connecté.")
            return
        self.client.publish(topic, payload, qos=qos, retain=retain)

    def stop(self):
        """À appeler à la fermeture de l'appli pour quitter proprement."""
        self.client.disconnect()
        self.quit()
        self.wait()
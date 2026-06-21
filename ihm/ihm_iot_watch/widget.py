# This Python file uses the following encoding: utf-8
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from MqttWorker import MqttWorker

class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- UI minimale pour test ---
        self.status_label = QLabel("MQTT : déconnecté")
        self.data_label = QLabel("En attente de données...")

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.data_label)

        # --- Initialisation du worker MQTT ---
        self.mqtt_worker = MqttWorker(
            broker_host="localhost",   # adapte à ton broker
            port=1883,
            topics=["mon/topic/#"],    # adapte à tes topics
        )

        # Connexion des signaux du worker aux slots de l'UI
        self.mqtt_worker.connected.connect(self._on_mqtt_connected)
        self.mqtt_worker.disconnected.connect(self._on_mqtt_disconnected)
        self.mqtt_worker.message_received.connect(self._on_mqtt_message)

        # Démarrage du thread (appelle run() en arrière-plan)
        self.mqtt_worker.start()

    def _on_mqtt_connected(self):
        self.status_label.setText("MQTT : connecté")

    def _on_mqtt_disconnected(self):
        self.status_label.setText("MQTT : déconnecté")

    def _on_mqtt_message(self, topic: str, payload: bytes):
        """Reçu dans le thread UI grâce au signal Qt — sûr de modifier les widgets ici."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = payload.decode("utf-8", errors="replace")

        # ICI : appelle tes fonctions de traitement existantes, par exemple :
        # resultat = mon_module.traiter(data)

        self.data_label.setText(f"{topic} → {data}")

    def closeEvent(self, event):
        """Arrête proprement le thread MQTT à la fermeture de la fenêtre."""
        self.mqtt_worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    window = Widget()
    window.show()
    sys.exit(app.exec())


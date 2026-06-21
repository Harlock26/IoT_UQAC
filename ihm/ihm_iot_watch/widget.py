# This Python file uses the following encoding: utf-8
import sys
import json

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel
import pyqtgraph as pg

from MqttWorker import MqttWorker
from HeartRateCalculator import HeartRateCalculator


class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- UI ---
        self.status_label = QLabel("MQTT : déconnecté")
        self.data_label = QLabel("En attente de données...")

        # Graphe temps réel pour la fenêtre glissante du signal cardiaque
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle("Signal cardiaque (fenêtre glissante)")
        self.plot_widget.setLabel("left", "Amplitude")
        self.plot_widget.setLabel("bottom", "Échantillon")
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color="g", width=2))

        # Graphe du spectre fréquentiel (FFT), affiché à droite du graphe temporel
        self.spectrum_plot_widget = pg.PlotWidget()
        self.spectrum_plot_widget.setTitle("Spectre fréquentiel")
        self.spectrum_plot_widget.setLabel("left", "Amplitude")
        self.spectrum_plot_widget.setLabel("bottom", "Fréquence (Hz)")
        self.spectrum_curve = self.spectrum_plot_widget.plot(pen=pg.mkPen(color="m", width=2))

        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.plot_widget)
        plots_layout.addWidget(self.spectrum_plot_widget)

        # Label BPM, agrandi pour bien le voir, couleur dynamique
        self.bpm_label = QLabel("BPM : --")
        self.bpm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: black;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.data_label)
        layout.addLayout(plots_layout)
        layout.addWidget(self.bpm_label)

        # --- Initialisation du worker MQTT ---
        self.mqtt_worker = MqttWorker(
            broker_host="test.mosquitto.org",
            port=1883,
            topics=["acceleration", "heartrate"],
        )

        # --- Initialisation du calculateur de rythme cardiaque ---
        self.heartrate = HeartRateCalculator()
        self.last_bpm = None  # dernière valeur calculée connue

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

        self.data_label.setText(f"{topic} → {data}")

        if topic == "heartrate":
            self._handle_heartrate(data)

    def _handle_heartrate(self, data):
        """Traite les nouvelles données heartrate, met à jour le graphe
        et le BPM affiché."""
        # data doit être un itérable d'échantillons (ex: liste de floats)
        if not isinstance(data, (list, tuple)):
            data = [data]

        resultat = self.heartrate.on_new_data(data)

        if resultat is False:
            # Valeurs aberrantes : on garde l'affichage du dernier BPM connu, en rouge
            self._set_bpm_display(self.last_bpm, valid=False)
        else:
            # resultat contient le nouveau BPM calculé
            self.last_bpm = resultat
            self._set_bpm_display(self.last_bpm, valid=True)

            # Publication du résultat sur le broker MQTT
            self.mqtt_worker.publish("heartrate/bpm", f"{resultat:.1f}")

        # Le graphe affiche toujours la fenêtre glissante courante,
        # qu'elle ait été jugée valide ou non (utile pour voir le signal brut)
        self._update_plot()

    def _update_plot(self):
        buffer = self.heartrate.buffer
        if len(buffer) > 15:
            filtered_buffer = self.heartrate.lowpass_filter(buffer)
            self.curve.setData(list(range(len(filtered_buffer))), filtered_buffer)

        # Mise à jour du graphe de spectre avec le dernier spectre calculé
        # (rempli par HeartRateCalculator.on_new_data lorsque le buffer est suffisant)
        if len(self.heartrate.last_freqs) > 0:
            self.spectrum_curve.setData(self.heartrate.last_freqs, self.heartrate.last_spectre)

    def _set_bpm_display(self, bpm, valid: bool):
        if bpm is None:
            self.bpm_label.setText("BPM : --")
            self.bpm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
            return

        self.bpm_label.setText(f"BPM : {bpm:.1f}")
        if valid:
            self.bpm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        else:
            self.bpm_label.setStyleSheet("font-size: 24px; font-weight: bold; color: red;")

    def closeEvent(self, event):
        """Arrête proprement le thread MQTT à la fermeture de la fenêtre."""
        self.mqtt_worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    window = Widget()
    window.show()
    sys.exit(app.exec())
# This Python file uses the following encoding: utf-8
import sys
import json

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
)
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import numpy as np

from MqttWorker import MqttWorker
from HeartRateCalculator import HeartRateCalculator
from Accelerometer import Accelerometer
from Utils import Utils


class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- UI ---
        self.status_label = QLabel("MQTT : déconnecté")
        self.data_label = QLabel("En attente de données...")

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_heartrate_tab(), "Rythme cardiaque")
        self.tabs.addTab(self._build_accelerometer_tab(), "Accéléromètre")
        self.tabs.addTab(self._build_accelerometer_3d_tab(), "Accéléromètre 3D")

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.data_label)
        layout.addWidget(self.tabs)

        # --- Initialisation du worker MQTT ---
        self.mqtt_worker = MqttWorker(
            broker_host="test.mosquitto.org",
            port=1883,
            topics=["acceleration", "heartrate"],
        )

        # --- Initialisation des classes de traitement ---
        self.heartrate = HeartRateCalculator()
        self.accelerometer = Accelerometer()
        # self.utils = Utils()
        self.last_bpm = None  # dernière valeur calculée connue

        # Connexion des signaux du worker aux slots de l'UI
        self.mqtt_worker.connected.connect(self._on_mqtt_connected)
        self.mqtt_worker.disconnected.connect(self._on_mqtt_disconnected)
        self.mqtt_worker.message_received.connect(self._on_mqtt_message)

        # Démarrage du thread (appelle run() en arrière-plan)
        self.mqtt_worker.start()

    def _build_heartrate_tab(self):
        """Construit l'onglet rythme cardiaque (signal temporel + spectre + BPM)."""
        tab = QWidget()

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

        tab_layout = QVBoxLayout(tab)
        tab_layout.addLayout(plots_layout)
        tab_layout.addWidget(self.bpm_label)

        return tab

    def _build_accelerometer_tab(self):
        """Construit l'onglet accéléromètre (graphe temps réel des 3 axes x, y, z)."""
        tab = QWidget()

        self.accel_plot_widget = pg.PlotWidget()
        self.accel_plot_widget.setTitle("Accélération (x, y, z)")
        self.accel_plot_widget.setLabel("left", "Accélération")
        self.accel_plot_widget.setLabel("bottom", "Échantillon")
        self.accel_plot_widget.addLegend()

        self.curve_x = self.accel_plot_widget.plot(pen=pg.mkPen(color="r", width=2), name="x")
        self.curve_y = self.accel_plot_widget.plot(pen=pg.mkPen(color="g", width=2), name="y")
        self.curve_z = self.accel_plot_widget.plot(pen=pg.mkPen(color="b", width=2), name="z")

        self.speed_plot_widget = pg.PlotWidget()
        self.speed_plot_widget.setTitle("Vitesse (x, y, z)")
        self.speed_plot_widget.setLabel("left", "Vitesse")
        self.speed_plot_widget.setLabel("bottom", "Échantillon")
        self.speed_plot_widget.addLegend()

        self.curve_speed_x = self.speed_plot_widget.plot(pen=pg.mkPen(color="r", width=2), name="x")
        self.curve_speed_y = self.speed_plot_widget.plot(pen=pg.mkPen(color="g", width=2), name="y")
        self.curve_speed_z = self.speed_plot_widget.plot(pen=pg.mkPen(color="b", width=2), name="z")

        self.position_plot_widget = pg.PlotWidget()
        self.position_plot_widget.setTitle("Position (x, y, z)")
        self.position_plot_widget.setLabel("left", "Position")
        self.position_plot_widget.setLabel("bottom", "Échantillon")
        self.position_plot_widget.addLegend()

        self.curve_position_x = self.position_plot_widget.plot(pen=pg.mkPen(color="r", width=2), name="x")
        self.curve_position_y = self.position_plot_widget.plot(pen=pg.mkPen(color="g", width=2), name="y")
        self.curve_position_z = self.position_plot_widget.plot(pen=pg.mkPen(color="b", width=2), name="z")

        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.accel_plot_widget)
        plots_layout.addWidget(self.speed_plot_widget)
        plots_layout.addWidget(self.position_plot_widget)

        tab_layout = QVBoxLayout(tab)
        tab_layout.addLayout(plots_layout)

        return tab

    def _make_gl_view(self, title):
        """Crée un GLViewWidget configuré avec une grille, des axes,
        et une GLLinePlotItem pour tracer une trajectoire 3D (x, y, z)."""
        view = gl.GLViewWidget()
        view.setCameraPosition(distance=5)

        grid = gl.GLGridItem()
        view.addItem(grid)

        axis = gl.GLAxisItem()
        axis.setSize(2, 2, 2)
        view.addItem(axis)

        curve = gl.GLLinePlotItem(pos=np.zeros((1, 3)), color=(1, 1, 1, 1), width=2, antialias=True)
        view.addItem(curve)

        return view, curve

    def _build_accelerometer_3d_tab(self):
        """Construit l'onglet accéléromètre 3D : 3 trajectoires (x, y, z)
        affichées en 3D (accélération, vitesse, position)."""
        tab = QWidget()

        self.gl_accel_view, self.gl_accel_curve = self._make_gl_view("Accélération 3D")
        self.gl_speed_view, self.gl_speed_curve = self._make_gl_view("Vitesse 3D")
        self.gl_position_view, self.gl_position_curve = self._make_gl_view("Position 3D")

        accel_layout = QVBoxLayout()
        accel_layout.addWidget(QLabel("Accélération (x, y, z)"))
        accel_layout.addWidget(self.gl_accel_view)

        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("Vitesse (x, y, z)"))
        speed_layout.addWidget(self.gl_speed_view)

        position_layout = QVBoxLayout()
        position_layout.addWidget(QLabel("Position (x, y, z)"))
        position_layout.addWidget(self.gl_position_view)

        plots_layout = QHBoxLayout()
        plots_layout.addLayout(accel_layout)
        plots_layout.addLayout(speed_layout)
        plots_layout.addLayout(position_layout)

        tab_layout = QVBoxLayout(tab)
        tab_layout.addLayout(plots_layout)

        return tab
        self.status_label.setText("MQTT : connecté")

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
        elif topic == "acceleration":
            self._handle_acceleration(data)

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

    def _handle_acceleration(self, data):
        """Traite les nouvelles données d'accélération (x, y, z)
        et met à jour le graphe correspondant."""
        ok = self.accelerometer.on_new_data(data)
        if ok:
            self._update_accel_plot()

    def _update_accel_plot(self):
        x = self.accelerometer.buffer_x
        y = self.accelerometer.buffer_y
        z = self.accelerometer.buffer_z

        x_speed = self.accelerometer.speed_buffer_x
        y_speed = self.accelerometer.speed_buffer_y
        z_speed = self.accelerometer.speed_buffer_z

        x_position = self.accelerometer.position_buffer_x
        y_position = self.accelerometer.position_buffer_y
        z_position = self.accelerometer.position_buffer_z

        self.curve_x.setData(list(range(len(x))), x)
        self.curve_y.setData(list(range(len(y))), y)
        self.curve_z.setData(list(range(len(z))), z)

        self.curve_speed_x.setData(list(range(len(x))), x_speed)
        self.curve_speed_y.setData(list(range(len(y))), y_speed)
        self.curve_speed_z.setData(list(range(len(z))), z_speed)

        self.curve_position_x.setData(list(range(len(x))), x_position)
        self.curve_position_y.setData(list(range(len(y))), y_position)
        self.curve_position_z.setData(list(range(len(z))), z_position)

        self._update_accel_3d_plot(x, y, z, x_speed, y_speed, z_speed, x_position, y_position, z_position)

    def _update_accel_3d_plot(self, x, y, z, x_speed, y_speed, z_speed, x_position, y_position, z_position):
        """Met à jour les 3 trajectoires 3D (accélération, vitesse, position)
        à partir des buffers x, y, z courants."""

        def to_pos_array(bx, by, bz):
            n = min(len(bx), len(by), len(bz))
            if n < 1:
                return np.zeros((1, 3))
            return np.column_stack([bx[-n:], by[-n:], bz[-n:]])

        self.gl_accel_curve.setData(pos=to_pos_array(x, y, z))
        self.gl_speed_curve.setData(pos=to_pos_array(x_speed, y_speed, z_speed))
        self.gl_position_curve.setData(pos=to_pos_array(x_position, y_position, z_position))

    def _update_plot(self):
        buffer = self.heartrate.buffer
        if len(buffer) > 15:
            filtered_buffer = Utils.lowpass_filter(buffer, pe = self.heartrate.pe)
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
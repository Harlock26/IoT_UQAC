# This Python file uses the following encoding: utf-8
import numpy as np
from scipy.integrate import cumulative_trapezoid
from Utils import Utils

class Accelerometer:
    """Gère la fenêtre glissante des données d'accélération (x, y, z)
    reçues sur le topic MQTT 'acceleration'."""

    def __init__(self, buffer_duration=10, max_buffer_duration=30, pe=0.2):
        self.pe = pe  # période d'échantillonnage (s)
        self.buffer_duration = buffer_duration  # secondes
        self.max_buffer_duration = max_buffer_duration  # secondes

        self.buffer_size = int(self.buffer_duration / self.pe)
        self.max_buffer_size = int(self.max_buffer_duration / self.pe)

        self.buffer_x = []
        self.buffer_y = []
        self.buffer_z = []

        self.ac_buffer_x = []
        self.ac_buffer_y = []
        self.ac_buffer_z = []

        self.speed_buffer_y = []
        self.speed_buffer_x = []
        self.speed_buffer_z = []

        self.position_buffer_x = []
        self.position_buffer_y = []
        self.position_buffer_z = []

    def on_new_data(self, data):
        """
        Méthode appelée lorsque l'IHM reçoit une nouvelle donnée sur le topic acceleration.
        data : tuple/liste [x, y, z]

        Retourne False si la donnée est mal formée (pas exactement 3 valeurs),
        True si la donnée a bien été ajoutée à la fenêtre glissante.
        """
        if data is None or len(data) != 3:
            print("Donnée d'accélération rejetée : format invalide (attendu [x, y, z]).")
            return False

        x, y, z = data

        self.buffer_x.append(x)
        self.buffer_y.append(y)
        self.buffer_z.append(z)

        # self.ac_buffer_y = Utils.lowpass_filter(Utils.remove_dc(self.buffer_y), self.pe)
        # self.ac_buffer_x = Utils.lowpass_filter(Utils.remove_dc(self.buffer_x), self.pe)
        # self.ac_buffer_z = Utils.lowpass_filter(Utils.remove_dc(self.buffer_z), self.pe)

        self.ac_buffer_y = Utils.remove_dc(self.buffer_y)
        self.ac_buffer_x = Utils.remove_dc(self.buffer_x)
        self.ac_buffer_z = Utils.remove_dc(self.buffer_z)

        # On garde seulement les max_buffer_size derniers échantillons (fenêtre glissante)
        for buf in (self.buffer_x, self.buffer_y, self.buffer_z):
            if len(buf) > self.max_buffer_size:
                del buf[0:len(buf) - self.max_buffer_size]

        self.integrate(self.ac_buffer_x, self.speed_buffer_x, self.position_buffer_x)
        self.integrate(self.ac_buffer_y, self.speed_buffer_y, self.position_buffer_y)
        self.integrate(self.ac_buffer_z, self.speed_buffer_z, self.position_buffer_z)

        return True

    def integrate(self, acc_buffer, spe_buffer, pos_buffer) :
        """
        Integrates acceleration buffer to fill speed buffer
        Integrates speed buffer to get position buffer

        Intégration trapézoïdale : spe_buffer et pos_buffer sont recalculés
        entièrement à partir de acc_buffer à chaque appel (modifiés en place),
        ce qui reste cohérent même si la fenêtre glissante perd ses anciens
        échantillons.
        """
        if len(acc_buffer) < 2:
            # Pas assez de points pour intégrer : on vide les buffers dérivés
            spe_buffer.clear()
            pos_buffer.clear()
            return spe_buffer, pos_buffer

        acc = np.asarray(acc_buffer, dtype=float)

        # Intégration de l'accélération -> vitesse (m/s)
        vitesse = cumulative_trapezoid(acc, dx=self.pe, initial=0.0)

        # Intégration de la vitesse -> position (m)
        position = cumulative_trapezoid(vitesse, dx=self.pe, initial=0.0)

        spe_buffer.clear()
        spe_buffer.extend(vitesse.tolist())

        pos_buffer.clear()
        pos_buffer.extend(position.tolist())

        return spe_buffer, pos_buffer


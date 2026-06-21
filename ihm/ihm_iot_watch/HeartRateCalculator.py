# This Python file uses the following encoding: utf-8
import numpy as np
from scipy.signal import butter, filtfilt
from numpy.fft import fft, fftfreq

class HeartRateCalculator:
    def __init__(self):
        self.pe = 0.2 # Période d'échantillonnage
        self.buffer_duration = 10 # secondes
        self.max_buffer_duration = 30 # secondes
        self.threshold = 0.3 # Seuil de dtéction des fréquences

        self.buffer_size = int(self.buffer_duration / self.pe)
        self.max_buffer_size = int(self.max_buffer_duration / self.pe)
        self.buffer = []
        self.start = 0
        self.end = 0

        # Dernier spectre calculé (pour affichage temps réel côté IHM)
        self.last_freqs = []
        self.last_spectre = []

    def on_new_data(self, data) :
        """
        Méthode appelée lorsque l'IHM reçoit une nouvelle donnée sur le topic heartrate
        Retourne False si les valeurs sont abérrantes --> indique à l'IHM de bloquer le rythme affiché, aucun nouveau rythme ne sera calculé
        Retourne True si les valeurs sont cohérantes --> indique à l'IHM qu'un nouveau rythme va être calculé
        """

        if not self.buffer_est_valide(data, valeur_min=-100, valeur_max=100):
            print("Buffer rejeté : valeurs aberrantes détectées.")
            self.buffer = []  # Réinitialisation du buffer (capteur probablement décroché)
            self.start += self.buffer_size
            self.end += self.buffer_size
            return False

        # On ajoute les NOUVEAUX échantillons un par un à la fenêtre glissante
        # (et non le chunk entier comme un seul bloc -> sinon le signal n'est plus continu)
        self.buffer.extend(data)

        # On garde seulement les max_buffer_size derniers échantillons (fenêtre glissante)
        if len(self.buffer) > self.max_buffer_size:
           del self.buffer[0:len(self.buffer) - self.max_buffer_size]

        # On attend d'avoir une fenêtre suffisamment grande avant de calculer la fréquence
        if len(self.buffer) < self.buffer_size:
            return False

        # On retire le DC sur l'ensemble de la fenêtre
        buffer_sans_dc = self.remove_dc(self.buffer)

        freqs, spectre = self.convert_to_freq(buffer_sans_dc)
        self.last_freqs = freqs
        self.last_spectre = np.abs(spectre)
        return self.calculate_frequency(freqs, np.abs(spectre), threshold = self.threshold) * 60 # Retourne le BPM
        # Would be better to emit a signal


    def buffer_est_valide(self, buffer, valeur_min=10, valeur_max=250):
        """
        Vérifie qu'un buffer ne contient pas de valeurs aberrantes.

        Le capteur envoie parfois des valeurs saturées (ex: 255) ou du bruit
        pur (ex: 1, 2, 3, 4, 5) quand le doigt n'est pas correctement posé.
        On rejette le buffer si une valeur sort de la plage plausible.

        Paramètres:
            buffer (array-like): le buffer à tester
            valeur_min (float): valeur minimale plausible
            valeur_max (float): valeur maximale plausible

        Retourne:
            bool: True si le buffer est valide, False sinon
        """
        buffer = np.asarray(buffer, dtype=float)
        if np.any(buffer < valeur_min) or np.any(buffer > valeur_max):
            return False
        return True

    def remove_dc(self, signal):
        """
        Supprime la composante continue (offset/moyenne) d'un signal discret.

        Paramètres
        ----------
        signal : array-like
            Le signal d'entrée (liste, tuple ou numpy array).

        Retour
        ------
        numpy.ndarray
            Le signal sans sa composante continue (moyenne nulle).
        """
        signal = np.asarray(signal, dtype=float)
        return signal - np.mean(signal)

    def convert_to_freq(self, buffer, freq_max_hz=2.5):
        """
        Calcule le spectre fréquentiel (FFT) d'un buffer.

        La période d'échantillonnage utilisée est self.pe (configurée
        sur l'instance), pour rester cohérente avec le reste du traitement.

        Retourne à la fois les fréquences ET les amplitudes du spectre
        (uniquement la partie des fréquences positives, le signal étant réel,
        et inférieures ou égales à freq_max_hz).
        """
        n = len(buffer)
        spectre = fft(buffer)
        freqs = fftfreq(n, d=self.pe)

        # On ne garde que les fréquences positives (le spectre est symétrique pour un signal réel)
        # et on exclut celles au-delà de freq_max_hz (2.5 Hz = 150 BPM, plage physiologique plausible)
        masque = (freqs > 0) & (freqs <= freq_max_hz)

        return freqs[masque], spectre[masque]


    def calculate_frequency(self, frequence, spectre, threshold=0.9):
        # Threshold = Seuil au dela duquel les valeurs sont prises en compte dans le calcul de la fréquence
        maximum = max(spectre)
        max_idx = np.argmax(spectre)
        freqs = []           # Contient toutes les fréquences prises en compte dans le calcul
        freqs_intensity = []  # Contient l'intensité de toutes les fréquences prises en compte dans le calcul (pour pondérer la moyenne)

        freqs.append(frequence[max_idx])
        freqs_intensity.append(maximum)

        # Remplissage des listes
        for i in range(0, len(spectre)):
            if spectre[i] > maximum * threshold and i != max_idx:
                freqs.append(frequence[i])
                freqs_intensity.append(spectre[i])

        # Calcul de la moyenne pondérée
        num = 0
        den = 0
        for i in range(0, len(freqs_intensity)):
            num += freqs_intensity[i] * freqs[i]
            den += freqs_intensity[i]

        average = num / den

        print(f"Fréquence dominante : {average}, soit {average * 60} bpm (threshold = {threshold})")
        return average


    def lowpass_filter(self, data, cutoff_hz=1.0, order=4):
        """
        Applique un filtre passe-bas Butterworth (zero-phase) à un signal.

        cutoff_hz : fréquence de coupure du filtre (Hz)
        order     : ordre du filtre

        La fréquence d'échantillonnage (fs_hz) est dérivée de self.pe
        pour rester cohérente avec le reste du traitement.
        """
        fs_hz = 1.0 / self.pe
        nyquist = 0.5 * fs_hz
        normal_cutoff = min(cutoff_hz / nyquist, 0.99)  # évite de dépasser la limite de Nyquist
        b, a = butter(order, normal_cutoff, btype="low", analog=False)
        return filtfilt(b, a, data)
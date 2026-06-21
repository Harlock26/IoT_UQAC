# This Python file uses the following encoding: utf-8
from scipy.signal import butter, filtfilt
import numpy as np


class Utils:
    def __init__(self):
        pass

    @staticmethod
    def lowpass_filter(data,pe = 0.2, cutoff_hz=1.0, order=4):
        """
        Applique un filtre passe-bas Butterworth (zero-phase) à un signal.

        cutoff_hz : fréquence de coupure du filtre (Hz)
        order     : ordre du filtre

        La fréquence d'échantillonnage (fs_hz) est dérivée de self.pe
        pour rester cohérente avec le reste du traitement.
        """
        fs_hz = 1.0 / pe
        nyquist = 0.5 * fs_hz
        normal_cutoff = min(cutoff_hz / nyquist, 0.99)  # évite de dépasser la limite de Nyquist
        b, a = butter(order, normal_cutoff, btype="low", analog=False)
        return filtfilt(b, a, data)

    @staticmethod
    def remove_dc(signal) :
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





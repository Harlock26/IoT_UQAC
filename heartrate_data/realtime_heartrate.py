"""
Calcul le rythme cardiaque en temps réel
Récupère des buffers de valeurs au fur et à mesure dans un fichier txt
Rejette le buffer si les valeurs sont abérrantes
Calcul le rythme cardiaque si les valeurs sont cohérantes

Usage:
    python realtime_heartrate.py [chemin_du_fichier_log]

Si aucun chemin n'est fourni, le script utilise "heartrate_log.txt"
dans le même dossier.
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
from numpy.fft import fft, fftfreq

def extraire_valeurs(chemin_fichier):
    """
    Lit un fichier texte et retourne une liste contenant chaque ligne du fichier.

    Paramètres:
        chemin_fichier (str): le chemin vers le fichier .txt

    Retourne:
        list[float]: une liste où chaque élément correspond à une valeur numérique du fichier
    """
    valeurs = []
    with open(chemin_fichier, 'r', encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                valeurs.append(int(ligne))
            except ValueError:
                try:
                    valeurs.append(float(ligne))
                except ValueError:
                    continue
    return valeurs

def buffer_est_valide(buffer, valeur_min=10, valeur_max=250):
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

def calculate_frequency(frequence, spectre, threshold=0.9):
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

def convert_to_freq(buffer, periode_echantillonnage_s=0.2):
    """
    Calcule le spectre fréquentiel (FFT) d'un buffer.

    Retourne à la fois les fréquences ET les amplitudes du spectre
    (uniquement la partie des fréquences positives, le signal étant réel).
    """
    n = len(buffer)
    spectre = fft(buffer)
    freqs = fftfreq(n, d=periode_echantillonnage_s)

    # On ne garde que les fréquences positives (le spectre est symétrique pour un signal réel)
    masque_positif = freqs > 0

    return freqs[masque_positif], spectre[masque_positif]

def remove_dc(signal):
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

def lowpass_filter(data, cutoff_hz=1.0, fs_hz=5.0, order=4):
    """
    Applique un filtre passe-bas Butterworth (zero-phase) à un signal.

    cutoff_hz : fréquence de coupure du filtre (Hz)
    fs_hz     : fréquence d'échantillonnage du signal (Hz)
    order     : ordre du filtre
    """
    nyquist = 0.5 * fs_hz
    normal_cutoff = min(cutoff_hz / nyquist, 0.99)  # évite de dépasser la limite de Nyquist
    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    return filtfilt(b, a, data)

def tracer(buffer, freqs, spectre, periode_echantillonnage_s=0.2):
    # Filtrage du signal temporel (buffer)
    fs = 1 / periode_echantillonnage_s  # 5Hz --> Les valeurs sont mesurées toutes les 200ms
    cutoff = 1.5  # Hz, à ajuster selon le besoin (doit être < fs/2)
    buffer_sans_dc = remove_dc(buffer)
    buffer_filtre = lowpass_filter(buffer_sans_dc, cutoff_hz=cutoff, fs_hz=fs)

    t = np.arange(len(buffer)) * periode_echantillonnage_s

    # Tracé temporel
    fig, axs = plt.subplots(2, figsize=(14, 6))
    axs[0].set_title("Évolution du flux sanguin")
    axs[0].set_xlabel("Temps (s)")
    axs[0].set_ylabel("Blood flow")
    axs[0].plot(t, buffer_sans_dc, color="tab:blue", alpha=0.5, label="Signal brut (sans DC)")
    axs[0].plot(t, buffer_filtre, color="tab:green", linewidth=2, label="Signal filtré (passe-bas)")
    axs[0].grid(True, alpha=0.3)
    axs[0].legend()

    # Tracé fréquentiel
    axs[1].plot(freqs, np.abs(spectre), color="tab:red", linewidth=1, label="Spectre (valeurs non filtrées)")
    axs[1].set_title("Fréquences cardiaques")
    axs[1].set_xlabel("Fréquence (Hz)")
    axs[1].set_ylabel("Intensité")
    axs[1].grid(True, alpha=0.3)
    axs[1].legend()

    fig.tight_layout()
    plt.show()

if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "heartrate_log.txt"
    valeurs = extraire_valeurs(chemin)

    buffer_size = 50 # 50 * 0.2s de période = 10s de buffer
    max_buffer_size = 300 # 60s
    buffer = []

    start = 0
    end = buffer_size

    for i in range(0, int(len(valeurs) / buffer_size)):
        nouveau_chunk = valeurs[start:end]

        if not buffer_est_valide(nouveau_chunk, valeur_min=-100, valeur_max=100):
            print(f"Buffer {i} rejeté : valeurs aberrantes détectées.")
            buffer = []  # Réinitialisation du buffer (capteur probablement décroché)
            start += buffer_size
            end += buffer_size
            continue

        # On ajoute les NOUVEAUX échantillons un par un à la fenêtre glissante
        # (et non le chunk entier comme un seul bloc -> sinon le signal n'est plus continu)
        buffer.extend(nouveau_chunk)

        # On garde seulement les max_buffer_size derniers échantillons (fenêtre glissante)
        if len(buffer) > max_buffer_size:
            del buffer[0:len(buffer) - max_buffer_size]

        # On attend d'avoir une fenêtre suffisamment grande avant de calculer la fréquence
        if len(buffer) < buffer_size:
            start += buffer_size
            end += buffer_size
            continue

        # On retire le DC sur l'ensemble de la fenêtre (pas chunk par chunk)
        buffer_sans_dc = remove_dc(buffer)

        freqs, spectre = convert_to_freq(buffer_sans_dc)
        calculate_frequency(freqs, np.abs(spectre), threshold=0.6)
        tracer(buffer, freqs, spectre)

        start += buffer_size
        end += buffer_size
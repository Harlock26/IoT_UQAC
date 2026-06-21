"""
Trace les valeurs de heartratePinValue extraites d'un fichier de log.

Usage:
    python plot_heartrate.py [chemin_du_fichier_log]

Si aucun chemin n'est fourni, le script utilise "heartrate_log.txt"
dans le même dossier.
"""

import re
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
from numpy.fft import fft, fftfreq


# def extraire_valeurs(chemin_fichier):
#     """Extrait toutes les valeurs numériques associées à heartratePinValue."""
#     valeurs = []
#     pattern = re.compile(r"heartratePinValue\s*=\s*(-?\d+)")

#     with open(chemin_fichier, "r", encoding="utf-8") as f:
#         for ligne in f:
#             match = pattern.search(ligne)
#             if match:
#                 valeurs.append(int(match.group(1)))

#     return valeurs

def extraire_valeurs(chemin_fichier):
    """
    Lit un fichier texte et retourne une liste contenant chaque ligne du fichier.
    
    Paramètres:
        chemin_fichier (str): le chemin vers le fichier .txt
    
    Retourne:
        list[str]: une liste où chaque élément correspond à une ligne du fichier
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

def calculate_frequency(frequence, spectre, threshold = 0.9) : 
    # Threshold = Seuil au dela duquel les valeurs sont prises en compte dans le calcul de la fréquence
    maximum = max(spectre)
    max_idx = np.argmax(spectre)
    freqs = [] # Contient toutes les fréquences prises en compte dans le calcul
    freqs_intensity = [] # Contient l'intensité de toutes les fréquences prises en compte dans le calcul (pour pondérer la moyenne)

    freqs.append(frequence[max_idx])
    freqs_intensity.append(maximum)

    # Remplissage des listes
    for i in range(0,len(spectre)) : 
        if spectre[i] > maximum * threshold : 
            freqs.append(frequence[i])
            freqs_intensity.append(spectre[i])

    # print("freqs = ", freqs)
    # print("freqs_intensity = ", freqs_intensity)

    # Calcul de la moyenne pondérée
    num = 0
    den = 0
    for i in range(0,len(freqs_intensity)) : 
        num += freqs_intensity[i] * freqs[i]
        den += freqs_intensity[i]

    average = num / den

    print(f"Fréquence dominante : {average}, soit {average * 60} bpm (threshold = {threshold})")



def tracer(valeurs, valeur_max_invalide=255, periode_echantillonnage_s=0.2):
    """Affiche un graphique des valeurs, avec mise en évidence des données invalides."""
    temps = [i * periode_echantillonnage_s for i in range(len(valeurs))]

    # Paramètres du filtre passe-bas
    fs = 1 / periode_echantillonnage_s  # 5Hz --> Les valeurs sont mesurées toutes les 200ms
    cutoff = 1.5  # Hz, à ajuster selon le besoin (doit être < fs/2)

    valeurs_filtrees = lowpass_filter(remove_dc(valeurs), cutoff_hz=cutoff, fs_hz=fs)

    fig, axs = plt.subplots(2, figsize=(14, 6))

    # --- Tracé temporel ---
    axs[0].plot(temps, valeurs_filtrees, color="tab:red", linewidth=1, label="heartratePinValue")

    # Mise en évidence des valeurs suspectes (ex: 255 = capteur déconnecté/erreur)
    invalides_x = [i * periode_echantillonnage_s for i, v in enumerate(valeurs) if v >= valeur_max_invalide]
    invalides_y = [v for v in valeurs if v >= valeur_max_invalide]
    if invalides_x:
        axs[0].scatter(invalides_x, invalides_y, color="black", marker="x",
                        label=f"Valeurs invalides (>= {valeur_max_invalide})", zorder=5)

    axs[0].set_title("Évolution du flux sanguin")
    axs[0].set_xlabel("Temps (s)")
    axs[0].set_ylabel("Blood flow")
    axs[0].grid(True, alpha=0.3)
    axs[0].legend()

    # --- Tracé fréquentiel ---
    n = len(valeurs_filtrees)
    spectre = fft(valeurs_filtrees)
    freqs = fftfreq(n, d=periode_echantillonnage_s)

    # --- Tracé fréquentiel non-filtré ---
    spectre_brut = fft(valeurs)
    freqs_brut = fftfreq(n, d=periode_echantillonnage_s)


    # On ne garde que les fréquences positives (le spectre est symétrique pour un signal réel)
    masque_positif = freqs > 0
    masque_brut_positif = freqs_brut > 0

    axs[1].plot(freqs[masque_positif], np.abs(spectre[masque_positif]),
                color="tab:red", linewidth=1, label="fréquence des valeurs filtrées")
    axs[1].plot(freqs[masque_brut_positif], np.abs(spectre[masque_brut_positif]),
                color="tab:blue", linewidth=1, label="fréquence des valeurs non-filtrées")
    axs[1].set_title("Fréquences cardiaques")
    axs[1].set_xlabel("Fréquence (Hz)")
    axs[1].set_ylabel("Intensité")
    axs[1].grid(True, alpha=0.3)
    axs[1].legend()

    # --- Trouver la fréquence dominante ---
    freq_idx = np.argmax(spectre[masque_positif])
    print("freq_idx = ", freq_idx)
    freq_dominante = freqs[freq_idx + 1]
    print(f"[1] Fréquence dominante : {freq_dominante}, soit {freq_dominante * 60} bpm")

    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.1)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.2)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.3)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.4)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.5)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.6)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.7)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.8)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 0.9)
    calculate_frequency(freqs[masque_positif], np.abs(spectre[masque_positif]), threshold = 1)


    fig.tight_layout()
    fig.savefig("heartrate_plot.png", dpi=150)
    print(f"{len(valeurs)} valeurs tracées. Graphique sauvegardé sous heartrate_plot.png")
    plt.show()


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "heartrate_log.txt"
    valeurs = extraire_valeurs(chemin)

    if not valeurs:
        print("Aucune valeur 'heartratePinValue' trouvée dans le fichier.")
        sys.exit(1)

    tracer(valeurs)
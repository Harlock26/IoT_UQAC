"""
Trace les valeurs de heartratePinValue extraites d'un fichier de log.

Usage:
    python plot_heartrate.py [chemin_du_fichier_log]

Si aucun chemin n'est fourni, le script utilise "heartrate_log.txt"
dans le même dossier.
"""

import re
import sys
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt


def extraire_valeurs(chemin_fichier):
    """Extrait toutes les valeurs numériques associées à heartratePinValue."""
    valeurs = []
    pattern = re.compile(r"heartratePinValue\s*=\s*(-?\d+)")

    with open(chemin_fichier, "r", encoding="utf-8") as f:
        for ligne in f:
            match = pattern.search(ligne)
            if match:
                valeurs.append(int(match.group(1)))

    return valeurs


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


def tracer(valeurs, valeur_max_invalide=255, periode_echantillonnage_s=0.2):
    """Affiche un graphique des valeurs, avec mise en évidence des données invalides."""
    temps = [i * periode_echantillonnage_s for i in range(len(valeurs))]

    plt.figure(figsize=(14, 6))

    # Paramètres du filtre passe-bas
    fs = 1 / periode_echantillonnage_s  # 5Hz --> Les valeurs sont mesurées toutes les 200ms
    cutoff = 1.5  # Hz, à ajuster selon le besoin (doit être < fs/2)

    # Tracé principal
    plt.plot(temps, lowpass_filter(valeurs, cutoff_hz=cutoff, fs_hz=fs), color="tab:red", linewidth=1, label="heartratePinValue")

    # Mise en évidence des valeurs suspectes (ex: 255 = capteur déconnecté/erreur)
    invalides_x = [i * periode_echantillonnage_s for i, v in enumerate(valeurs) if v >= valeur_max_invalide]
    invalides_y = [v for v in valeurs if v >= valeur_max_invalide]
    if invalides_x:
        plt.scatter(invalides_x, invalides_y, color="black", marker="x",
                    label=f"Valeurs invalides (>= {valeur_max_invalide})", zorder=5)

    plt.title("Évolution de heartratePinValue")
    plt.xlabel("Temps (s)")
    plt.ylabel("heartratePinValue")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.savefig("heartrate_plot.png", dpi=150)
    print(f"{len(valeurs)} valeurs tracées. Graphique sauvegardé sous heartrate_plot.png")
    plt.show()


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "heartrate_log.txt"
    valeurs = extraire_valeurs(chemin)

    if not valeurs:
        print("Aucune valeur 'heartratePinValue' trouvée dans le fichier.")
        sys.exit(1)

    tracer(valeurs)
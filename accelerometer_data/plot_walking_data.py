"""
Trace les courbes x, y et z d'un fichier CSV de données de marche
sur un même graphe en fonction du temps.

Utilisation :
    python plot_walking_data.py walking_data.csv
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt


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


def main(csv_path: str):
    # Lecture du CSV
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    # Estimation de la fréquence d'échantillonnage à partir des timestamps
    # dt = df["timestamp"].diff().dt.total_seconds().median()
    # fs = 1.0 / dt
    # print(f"Fréquence d'échantillonnage estimée : {fs:.2f} Hz")

    fs = 5

    # Application du filtre passe-bas sur x, y, z
    cutoff = 0.4  # Hz, à ajuster selon le besoin (doit être < fs/2)
    df["x_filt"] = lowpass_filter(df["x"], cutoff_hz=cutoff, fs_hz=fs)
    df["y_filt"] = lowpass_filter(df["y"], cutoff_hz=cutoff, fs_hz=fs)
    df["z_filt"] = lowpass_filter(df["z"], cutoff_hz=cutoff, fs_hz=fs)

    # df["x_filt"] = df["x"]
    # df["y_filt"] = df["y"]
    # df["z_filt"] = df["z"]

    # Création du graphe
    plt.figure(figsize=(12, 6))
    plt.plot(df["timestamp"], df["x_filt"], label="x", linewidth=1)
    plt.plot(df["timestamp"], df["y_filt"], label="y", linewidth=1)
    plt.plot(df["timestamp"], df["z_filt"], label="z", linewidth=1)

    plt.ylim(-500, 1500)
    # plt.xlim(185, 262)
    plt.xlabel("Temps")
    plt.ylabel("Valeur")
    plt.title("Accélération x, y, z filtrée (passe-bas) en fonction du temps")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig("walking_data_plot.png", dpi=150)
    plt.show()


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "walking_data.csv"
    main(csv_file)

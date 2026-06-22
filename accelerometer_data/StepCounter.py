"""
Compteur de cycles de marche basé sur les données d'accéléromètre.

Pattern d'un cycle (Figure 1, Zhao 2010) :
  - Axe Z (vertical)   : augmentation → diminution
  - Axe Y (avant)      : diminution → augmentation (légèrement décalé par rapport à Z)

Stratégie :
  1. Filtrage passe-bas pour éliminer le bruit haute fréquence.
  2. Soustraction de la gravité sur Z (moyenne glissante longue).
  3. Détection des pics positifs sur Z filtré → chaque pic = demi-cycle "appui".
  4. Validation croisée avec Y : on vérifie qu'un creux (valeur négative) sur Y
     se produit dans une fenêtre de temps autour du pic Z, ce qui confirme
     que c'est bien un pas et non un artefact.
  5. Anti-rebond temporel : deux pics valides doivent être séparés d'au moins
     MIN_STEP_INTERVAL secondes.
"""

from collections import deque
import time
import math


# ──────────────────────────────────────────────
# Paramètres (à ajuster selon votre matériel)
# ──────────────────────────────────────────────
SAMPLE_RATE_HZ       = 50       # fréquence d'échantillonnage attendue
LOWPASS_ALPHA        = 0.2      # lissage exponentiel (0 = très lisse, 1 = aucun lissage)
GRAVITY_ALPHA        = 0.02     # lissage très lent pour estimer la gravité sur Z
PEAK_THRESHOLD_Z     = 0.3      # seuil minimal du pic Z filtré (en g ou m/s², même unité que le capteur)
VALLEY_THRESHOLD_Y   = -0.15    # seuil maximal du creux Y pour validation croisée
CROSS_WINDOW_SAMPLES = 15       # fenêtre (en échantillons) autour du pic Z pour chercher le creux Y
MIN_STEP_INTERVAL    = 0.3      # secondes minimales entre deux pas valides


class StepCounter:
    """
    Compteur de cycles de marche en temps réel.

    Utilisation :
        counter = StepCounter()
        # dans votre boucle de lecture du capteur :
        counter.update(ax, ay, az)          # ax, ay, az en g ou m/s² (cohérence avec les seuils)
        print(counter.step_count)
    """

    def __init__(self,
                 sample_rate: float   = SAMPLE_RATE_HZ,
                 lowpass_alpha: float = LOWPASS_ALPHA,
                 gravity_alpha: float = GRAVITY_ALPHA,
                 peak_threshold_z: float   = PEAK_THRESHOLD_Z,
                 valley_threshold_y: float = VALLEY_THRESHOLD_Y,
                 cross_window_samples: int = CROSS_WINDOW_SAMPLES,
                 min_step_interval: float  = MIN_STEP_INTERVAL):

        self.sample_rate        = sample_rate
        self.lp_alpha           = lowpass_alpha
        self.grav_alpha         = gravity_alpha
        self.peak_thr_z         = peak_threshold_z
        self.valley_thr_y       = valley_threshold_y
        self.cross_win          = cross_window_samples
        self.min_step_samples   = int(min_step_interval * sample_rate)

        # État des filtres
        self._lp_z   = 0.0
        self._lp_y   = 0.0
        self._grav_z = None        # initialisé au premier échantillon

        # Buffers circulaires pour la fenêtre de validation croisée
        self._buf_z: deque = deque(maxlen=cross_window_samples * 2 + 1)
        self._buf_y: deque = deque(maxlen=cross_window_samples * 2 + 1)

        # Suivi des pics
        self._sample_index      = 0
        self._last_step_sample  = -self.min_step_samples  # permet un pas dès le début
        self._prev_lp_z         = 0.0
        self._rising_z          = False

        # Résultat
        self.step_count = 0

    # ──────────────────────────────────────────
    # Méthode principale : appeler à chaque échantillon
    # ──────────────────────────────────────────
    def update(self, ax: float, ay: float, az: float) -> bool:
        """
        Traite un nouvel échantillon (ax, ay, az).

        Retourne True si un nouveau cycle de marche vient d'être détecté.
        """
        # 1. Initialisation de la gravité
        if self._grav_z is None:
            self._grav_z = az

        # 2. Estimation glissante de la gravité sur Z (composante DC)
        self._grav_z = (1 - self.grav_alpha) * self._grav_z + self.grav_alpha * az

        # 3. Suppression de la gravité puis lissage passe-bas
        az_dynamic = az - self._grav_z
        self._lp_z = (1 - self.lp_alpha) * self._lp_z + self.lp_alpha * az_dynamic
        self._lp_y = (1 - self.lp_alpha) * self._lp_y + self.lp_alpha * ay

        # 4. Stocker dans les buffers de validation croisée
        self._buf_z.append(self._lp_z)
        self._buf_y.append(self._lp_y)

        step_detected = False

        # 5. Détection de pic sur Z :
        #    Un pic = la valeur précédente était en montée ET la valeur actuelle redescend
        #    ET la valeur du pic dépasse le seuil.
        if self._rising_z and self._lp_z < self._prev_lp_z:
            # On vient de franchir un sommet
            peak_value = self._prev_lp_z
            if peak_value >= self.peak_thr_z:
                step_detected = self._validate_and_count()

        # Mise à jour de la direction
        self._rising_z = self._lp_z > self._prev_lp_z
        self._prev_lp_z = self._lp_z
        self._sample_index += 1

        return step_detected

    # ──────────────────────────────────────────
    # Validation croisée + anti-rebond
    # ──────────────────────────────────────────
    def _validate_and_count(self) -> bool:
        """
        Vérifie :
          a) anti-rebond temporel (pas trop rapproché du précédent)
          b) présence d'un creux sur Y dans la fenêtre autour du pic Z
        """
        # a) Anti-rebond
        if self._sample_index - self._last_step_sample < self.min_step_samples:
            return False

        # b) Validation croisée sur Y :
        #    Dans le buffer courant, chercher si au moins une valeur de Y
        #    est en dessous du seuil (creux de décélération vers l'avant).
        if min(self._buf_y) > self.valley_thr_y:
            return False

        # ✓ Pas validé
        self.step_count += 1
        self._last_step_sample = self._sample_index
        return True

    def reset(self):
        """Remet le compteur à zéro (garde les filtres initialisés)."""
        self.step_count = 0
        self._last_step_sample = -self.min_step_samples


# ══════════════════════════════════════════════════════════════════
# Simulation / test avec données synthétiques
# ══════════════════════════════════════════════════════════════════
def _simulate_walk(n_steps: int = 10, hz: int = 50) -> list[tuple[float, float, float]]:
    """
    Génère un signal synthétique imitant la marche (Zhao 2010) :
      - Z : sinusoïde positive (pic à chaque pas)
      - Y : sinusoïde négative décalée de ~π/4 (creux légèrement après le pic Z)
    """
    T_step  = 0.6          # durée d'un pas (s)
    samples_per_step = int(T_step * hz)
    total   = n_steps * samples_per_step
    data    = []

    for i in range(total):
        t = i / hz
        phase = 2 * math.pi * t / T_step

        # Gravité simulée (1 g sur Z) + dynamique de marche
        az = 1.0 + 0.5 * math.sin(phase)                     # pic positif sur Z
        ay =       0.4 * math.sin(phase - math.pi / 4)       # creux décalé sur Y
        ax = 0.0

        # Petit bruit gaussien
        import random
        az += random.gauss(0, 0.03)
        ay += random.gauss(0, 0.03)

        data.append((ax, ay, az))

    return data


if __name__ == "__main__":
    import random

    N_STEPS = 10
    print(f"=== Test de détection : {N_STEPS} pas simulés ===\n")

    counter = StepCounter(sample_rate=50)
    samples = _simulate_walk(n_steps=N_STEPS, hz=50)

    for i, (ax, ay, az) in enumerate(samples):
        detected = counter.update(ax, ay, az)
        if detected:
            t_s = i / 50
            print(f"  Pas #{counter.step_count:02d} détecté à t={t_s:.2f}s")

    print(f"\nRésultat : {counter.step_count} pas détectés pour {N_STEPS} pas simulés")
    accuracy = counter.step_count / N_STEPS * 100
    print(f"Précision approximative : {accuracy:.0f}%")

    print("\n=== Intégration dans votre boucle temps réel ===")
    print("""
counter = StepCounter()           # créer une fois

# Dans votre boucle de lecture :
while True:
    ax, ay, az = lire_accelerometre()   # votre fonction d'acquisition
    counter.update(ax, ay, az)
    print(f"Cycles de marche : {counter.step_count}")
""")
# This Python file uses the following encoding: utf-8
"""
Dh.py

Classe Dh : gère l'échange de secret Diffie-Hellman (ECDH) côté IHM, en
utilisant la même librairie C que la carte Arduino : tiny-ECDH-c
(https://github.com/kokke/tiny-ECDH-c).

Principe de l'échange (c'est l'Arduino qui initie) :
  1. L'Arduino génère sa paire de clés et publie sa clé publique (en hexa)
     sur le topic MQTT "dh/arduino".
  2. L'IHM reçoit ce message (via MqttWorker.message_received), génère sa
     propre paire de clés, calcule le secret partagé, puis publie sa propre
     clé publique (en hexa) sur le topic "dh/ihm".
  3. L'Arduino reçoit la clé publique de l'IHM et calcule le même secret
     partagé de son côté (voir le sketch Arduino).

La librairie C n'est pas réécrite en Python : on appelle directement les
fonctions ecdh_generate_keys() / ecdh_shared_secret() de ecdh.c via ctypes,
pour être certain d'utiliser exactement la même implémentation
cryptographique que la carte Arduino (et donc d'obtenir un secret partagé
identique des deux côtés, avec la même courbe).

Compilation de la librairie partagée (à faire une fois, voir aussi le
docstring tout en bas de ce fichier) :

    gcc -shared -fPIC -O2 -o libecdh.so ecdh.c

IMPORTANT : la courbe utilisée (macro ECC_CURVE dans ecdh.h, NIST_B163 par
défaut) doit être strictement identique entre l'Arduino et l'IHM, sinon
ECC_PRV_KEY_SIZE / ECC_PUB_KEY_SIZE ne correspondront pas et l'échange
échouera silencieusement ou plantera.
"""

import ctypes
import os
import secrets

from PySide6.QtCore import QObject, Signal

from MqttWorker import MqttWorker


# Tailles de clés pour la courbe par défaut de tiny-ECDH-c (NIST_B163 / NIST_K163).
# Si tu changes ECC_CURVE dans ecdh.h (côté C, Arduino ET IHM), mets aussi ces
# valeurs à jour ici (voir le tableau dans ecdh.h pour les autres courbes).
ECC_PRV_KEY_SIZE = 24
ECC_PUB_KEY_SIZE = 2 * ECC_PRV_KEY_SIZE  # = 48


def _bytes_to_hex(data: bytes) -> str:
    return data.hex()


def _hex_to_bytes(hex_str: str, expected_len: int) -> bytes:
    data = bytes.fromhex(hex_str)
    if len(data) != expected_len:
        raise ValueError(
            f"Longueur inattendue : {len(data)} octets reçus, {expected_len} attendus"
        )
    return data


class Dh(QObject):
    """Gère un échange Diffie-Hellman (ECDH) initié par la carte Arduino.

    Contrairement à une version précédente, cette classe NE s'abonne PAS
    elle-même au signal message_received du MqttWorker : c'est Widget qui
    reçoit tous les messages MQTT dans son propre slot _on_mqtt_message(),
    et qui doit explicitement appeler dh.handle_arduino_message(payload)
    lorsque topic == "dh/arduino".

    Usage typique (dans Widget.__init__, après création de mqtt_worker) :

        self.dh = Dh(self.mqtt_worker, lib_path="./libecdh.so")
        self.dh.secret_established.connect(self._on_dh_secret_established)
        self.dh.error.connect(self._on_dh_error)

    Puis, dans Widget._on_mqtt_message() :

        elif topic == "dh/arduino":
            self.dh.handle_arduino_message(payload)

    Le secret partagé final est exposé via self.dh.shared_secret (bytes)
    une fois established == True, et également émis par le signal
    secret_established pour réagir dans l'UI.
    """

    secret_established = Signal(bytes)
    error = Signal(str)

    TOPIC_ARDUINO = "dh/arduino"  # message envoyés par l'Arduino (clé publique Arduino)
    TOPIC_IHM = "dh/ihm"          # messages envoyés par l'IHM (clé publique IHM)

    def __init__(self, mqtt_worker: MqttWorker, lib_path="./libecdh.so", parent=None):
        super().__init__(parent)

        self.mqtt_worker = mqtt_worker
        self.established = False
        self.private_key = None
        self.public_key = None
        self.peer_public_key = None
        self.shared_secret = None

        self._lib = self._load_library(lib_path)

    # ------------------------------------------------------------------
    # Chargement de la librairie C via ctypes
    # ------------------------------------------------------------------
    def _load_library(self, lib_path):
        if not os.path.isfile(lib_path):
            raise FileNotFoundError(
                f"Librairie ECDH introuvable : {lib_path}. "
                f"Compile-la avec : gcc -shared -fPIC -O2 -o libecdh.so ecdh.c"
            )

        lib = ctypes.CDLL(os.path.abspath(lib_path))

        # int ecdh_generate_keys(uint8_t* public_key, uint8_t* private_key);
        lib.ecdh_generate_keys.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
        ]
        lib.ecdh_generate_keys.restype = ctypes.c_int

        # int ecdh_shared_secret(const uint8_t* private_key, const uint8_t* others_pub, uint8_t* output);
        lib.ecdh_shared_secret.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
        ]
        lib.ecdh_shared_secret.restype = ctypes.c_int

        return lib

    # ------------------------------------------------------------------
    # Génération de clés / calcul du secret, via la lib C
    # ------------------------------------------------------------------
    def _generate_keypair(self):
        """Génère la paire de clés ECDH de l'IHM.

        ecdh_generate_keys() attend que le buffer de clé privée contienne
        déjà des octets aléatoires avant l'appel (voir ecdh.h). On utilise
        secrets.token_bytes() (CSPRNG du système), contrairement au sketch
        Arduino qui utilise random()/analogRead() par manque de mieux —
        ici, sur l'IHM (PC), on a un vrai générateur cryptographique
        disponible, donc on l'utilise.
        """
        priv_buf = (ctypes.c_uint8 * ECC_PRV_KEY_SIZE)(*secrets.token_bytes(ECC_PRV_KEY_SIZE))
        pub_buf = (ctypes.c_uint8 * ECC_PUB_KEY_SIZE)()

        ret = self._lib.ecdh_generate_keys(pub_buf, priv_buf)
        if not ret:
            raise RuntimeError("ecdh_generate_keys a échoué")

        self.private_key = bytes(priv_buf)
        self.public_key = bytes(pub_buf)

    def _compute_shared_secret(self, peer_public_key: bytes):
        priv_buf = (ctypes.c_uint8 * ECC_PRV_KEY_SIZE)(*self.private_key)
        peer_buf = (ctypes.c_uint8 * ECC_PUB_KEY_SIZE)(*peer_public_key)
        secret_buf = (ctypes.c_uint8 * ECC_PUB_KEY_SIZE)()

        ret = self._lib.ecdh_shared_secret(priv_buf, peer_buf, secret_buf)
        if not ret:
            raise RuntimeError("ecdh_shared_secret a échoué")

        self.shared_secret = bytes(secret_buf)

    # ------------------------------------------------------------------
    # Point d'entrée appelé par Widget._on_mqtt_message() quand
    # topic == "dh/arduino"
    # ------------------------------------------------------------------
    def handle_arduino_message(self, payload: bytes):
        """À appeler depuis Widget._on_mqtt_message() lorsque le topic reçu
        est "dh/arduino". payload est la clé publique de l'Arduino, encodée
        en hexadécimal ASCII (cf. bytesToHex côté sketch Arduino)."""
        if self.established:
            # Échange déjà fait, on ignore les messages suivants (par ex.
            # si l'Arduino réémet sa clé publique faute de réponse reçue
            # à temps -- cf. dh_retryInterval côté sketch).
            return

        print("Beginning ecdh trade")
        self._handle_arduino_public_key(payload)

    def _handle_arduino_public_key(self, payload: bytes):
        try:
            hex_str = payload.decode("ascii")
            self.peer_public_key = _hex_to_bytes(hex_str, ECC_PUB_KEY_SIZE)
        except (UnicodeDecodeError, ValueError) as exc:
            self.error.emit(f"Clé publique Arduino invalide reçue sur {self.TOPIC_ARDUINO} : {exc}")
            return

        try:
            self._generate_keypair()
            self._compute_shared_secret(self.peer_public_key)
        except RuntimeError as exc:
            self.error.emit(str(exc))
            return

        self.established = True

        # On publie notre clé publique sur dh/ihm pour que l'Arduino
        # puisse calculer le même secret partagé de son côté.
        self.mqtt_worker.publish(self.TOPIC_IHM, _bytes_to_hex(self.public_key))

        self.secret_established.emit(self.shared_secret)
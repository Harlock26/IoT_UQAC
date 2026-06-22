# This Python file uses the following encoding: utf-8
import sqlite3
import time


class Database:
    """Gère la persistance des mesures (accéléromètre, heartrate, bpm)
    dans une base SQLite locale.

    Conçue pour être utilisée depuis un seul thread (le thread UI, qui
    reçoit déjà les données via les signaux Qt de MqttWorker) — pas de
    verrouillage supplémentaire nécessaire dans ce contexte."""

    def __init__(self, db_path="mesures.db"):
        self.db_path = db_path
        # check_same_thread=True (par défaut) : la connexion ne doit être
        # utilisée que depuis le thread qui l'a créée. C'est cohérent avec
        # notre cas, puisque save() est toujours appelé depuis le thread UI.
        self.connection = sqlite3.connect(self.db_path)
        self._create_table()

    def _create_table(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mesures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                type TEXT NOT NULL,
                valeur REAL NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mesures_type_timestamp
            ON mesures (type, timestamp)
            """
        )
        self.connection.commit()

    def save(self, type_mesure: str, valeur: float, timestamp: float = None):
        """Enregistre une mesure unique.

        type_mesure : ex. 'heartrate', 'bpm', 'acceleration_x', 'acceleration_y', 'acceleration_z'
        valeur      : la valeur numérique mesurée ou calculée
        timestamp   : epoch en secondes ; si None, l'heure actuelle est utilisée
        """
        if timestamp is None:
            timestamp = time.time()

        self.connection.execute(
            "INSERT INTO mesures (timestamp, type, valeur) VALUES (?, ?, ?)",
            (timestamp, type_mesure, float(valeur)),
        )
        self.connection.commit()

    def save_many(self, type_mesure: str, valeurs, timestamp: float = None):
        """Enregistre plusieurs valeurs du même type avec le même timestamp
        (utile par exemple pour un chunk d'échantillons heartrate reçus
        d'un coup)."""
        if timestamp is None:
            timestamp = time.time()

        rows = [(timestamp, type_mesure, float(v)) for v in valeurs]
        self.connection.executemany(
            "INSERT INTO mesures (timestamp, type, valeur) VALUES (?, ?, ?)",
            rows,
        )
        self.connection.commit()

    def fetch(self, type_mesure: str = None, limit: int = None):
        """Relit les mesures enregistrées, éventuellement filtrées par type,
        triées par timestamp croissant."""
        query = "SELECT timestamp, type, valeur FROM mesures"
        params = []

        if type_mesure is not None:
            query += " WHERE type = ?"
            params.append(type_mesure)

        query += " ORDER BY timestamp ASC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.connection.execute(query, params)
        return cursor.fetchall()

    def clear(self):
        """Supprime toutes les mesures enregistrées (tous types confondus :
        heartrate, bpm, acceleration_x/y/z, etc.)."""
        self.connection.execute("DELETE FROM mesures")
        self.connection.commit()

    def close(self):
        self.connection.close()
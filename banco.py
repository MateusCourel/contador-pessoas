"""Banco: guarda as pessoas cadastradas e seus embeddings no SQLite.

Só são guardados NÚMEROS (embeddings), nunca as fotos. O arquivo fica em
dados/pessoas.db, pasta que o .gitignore impede de subir para o GitHub.

Cada pessoa tem vários embeddings (um por pose). Para reconhecer, compara-se
o rosto novo com todos e fica-se com a melhor semelhança de cada pessoa.
"""
import os
import sqlite3
from datetime import datetime

import numpy as np

CAMINHO_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "dados", "pessoas.db")

# Semelhança de cosseno mínima para dizer "é a mesma pessoa" (valor
# recomendado pelo autor do modelo SFace). Maior = mais rígido.
LIMITE_RECONHECER = 0.363


def normalizar(vetor):
    v = np.asarray(vetor, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class Banco:
    def __init__(self, caminho=CAMINHO_PADRAO):
        if caminho != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(caminho)),
                        exist_ok=True)
        self._con = sqlite3.connect(caminho)
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                consentimento INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pessoa_id INTEGER NOT NULL
                    REFERENCES pessoas(id) ON DELETE CASCADE,
                pose TEXT NOT NULL,
                vetor BLOB NOT NULL
            );
        """)
        self._con.commit()

    def cadastrar(self, nome, embeddings, consentimento=True):
        """embeddings: dict {pose: vetor}. Devolve o id da nova pessoa."""
        nome = nome.strip()
        if not nome:
            raise ValueError("o nome não pode ficar vazio")
        if not embeddings:
            raise ValueError("nenhum embedding para guardar")
        if not consentimento:
            raise ValueError("sem consentimento não se cadastra")
        with self._con:
            cur = self._con.execute(
                "INSERT INTO pessoas (nome, criado_em, consentimento) "
                "VALUES (?, ?, ?)",
                (nome, datetime.now().isoformat(timespec="seconds"), 1))
            pid = cur.lastrowid
            for pose, vetor in embeddings.items():
                self._con.execute(
                    "INSERT INTO embeddings (pessoa_id, pose, vetor) "
                    "VALUES (?, ?, ?)",
                    (pid, pose, normalizar(vetor).tobytes()))
        return pid

    def listar(self):
        """[(id, nome, criado_em, quantidade_de_embeddings)]"""
        return self._con.execute("""
            SELECT p.id, p.nome, p.criado_em, COUNT(e.id)
            FROM pessoas p LEFT JOIN embeddings e ON e.pessoa_id = p.id
            GROUP BY p.id ORDER BY p.id""").fetchall()

    def existe_nome(self, nome):
        """True se já há alguém com esse nome (ignora maiúsculas e espaços)."""
        alvo = " ".join(nome.lower().split())
        return any(" ".join(n.lower().split()) == alvo
                   for _, n, _, _ in self.listar())

    def apagar(self, pessoa_id):
        """Apaga a pessoa e todos os embeddings dela. True se existia."""
        with self._con:
            cur = self._con.execute("DELETE FROM pessoas WHERE id = ?",
                                    (pessoa_id,))
        return cur.rowcount > 0

    def identificar(self, vetor, limite=LIMITE_RECONHECER):
        """Devolve (nome, semelhança). Se ninguém passar do limite,
        o nome é None (e a semelhança é a melhor encontrada)."""
        alvo = normalizar(vetor)
        melhor_nome, melhor = None, -1.0
        linhas = self._con.execute("""
            SELECT p.nome, e.vetor FROM embeddings e
            JOIN pessoas p ON p.id = e.pessoa_id""").fetchall()
        for nome, blob in linhas:
            sim = float(np.dot(alvo, np.frombuffer(blob, dtype=np.float32)))
            if sim > melhor:
                melhor_nome, melhor = nome, sim
        if melhor_nome is None:
            return None, 0.0
        return (melhor_nome if melhor >= limite else None), melhor

    def fechar(self):
        self._con.close()

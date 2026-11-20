#!/usr/bin/env python3
"""GOV Intelligence POC-18: importador manual de detalhes oficiais do PNCP.

Por padrao executa somente validacao (--aplicar necessario para gravar).
Nunca consulta a API, altera tabelas originais ou ativa agendamentos.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def instante(texto):
    if not isinstance(texto, str) or not texto:
        raise ValueError("Data de atualizacao ausente ou invalida")
    dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def carregar(arquivo):
    bruto = Path(arquivo).read_bytes()
    objeto = json.loads(bruto.decode("utf-8-sig"))
    if not isinstance(objeto, dict):
        raise ValueError("JSON detalhado deve ser objeto unico")
    ident = objeto.get("numeroControlePNCP")
    if not isinstance(ident, str) or not ident.strip():
        raise ValueError("numeroControlePNCP ausente")
    codigo = objeto.get("orcamentoSigilosoCodigo")
    if type(codigo) is not int or codigo not in (1, 2, 3):
        raise ValueError("Codigo de sigilo deve ser inteiro 1, 2 ou 3")
    fonte = objeto.get("dataAtualizacaoGlobal")
    instante(fonte)
    texto = bruto.decode("utf-8-sig")
    sha = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    return ident, codigo, fonte, sha, texto, objeto


def executar(banco, arquivo, aplicar=False):
    ident, codigo, data_fonte, sha, payload, documento = carregar(arquivo)
    # Modo sem escrita usa SQLite somente leitura.
    uri = f"file:{Path(banco).resolve().as_posix()}?mode={'rw' if aplicar else 'ro'}"
    with sqlite3.connect(uri, uri=True, timeout=15) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Integridade SQLite inicial reprovada")
        resumido = db.execute(
            "SELECT uf, payload_json FROM contratacoes WHERE id=?", (ident,)
        ).fetchone()
        if resumido is None:
            raise ValueError("Processo inexistente na base principal: " + ident)
        if resumido[0] != "CE":
            raise ValueError("Somente contratacoes CE autorizadas")
        dados_base = json.loads(resumido[1])
        data_base = dados_base.get("dataAtualizacaoGlobal")
        instante(data_base)
        if instante(data_fonte) < instante(data_base):
            raise ValueError("Detalhe anterior ao snapshot atual da contratacao; revisar antes de importar")
        if documento.get("unidadeOrgao") and isinstance(documento["unidadeOrgao"], dict):
            uf = documento["unidadeOrgao"].get("ufSigla")
            if uf is not None and uf != "CE":
                raise ValueError("UF divergente no detalhe PNCP")

        atual = db.execute(
            "SELECT payload_sha256, data_atualizacao_fonte FROM contratacoes_detalhes WHERE id=?",
            (ident,)
        ).fetchone()
        versao = db.execute(
            "SELECT 1 FROM contratacoes_detalhes_versoes WHERE id=? AND payload_sha256=?",
            (ident, sha)
        ).fetchone()
        if atual is None:
            estado = "PRIMEIRO_REGISTRO"
        elif atual[0] == sha:
            estado = "IDENTICO"
        elif instante(data_fonte) > instante(atual[1]):
            estado = "MAIS_RECENTE"
        elif instante(data_fonte) == instante(atual[1]):
            estado = "CONFLITO_MESMA_DATA"
        else:
            estado = "OBSOLETO"

        print("ID:", ident)
        print("Sigilo:", codigo, "|", documento.get("orcamentoSigilosoDescricao"))
        print("Data fonte:", data_fonte)
        print("SHA256:", sha)
        print("Estado:", estado)
        print("Versao ja conhecida:", bool(versao))

        if not aplicar:
            print("MODO: PRE-VISUALIZACAO, SEM GRAVAR")
            return

        # Validacao de versoes deve ocorrer ANTES de qualquer escrita.
        if versao and estado != "IDENTICO":
            # Versao historica conhecida: replay idempotente sem escrita.
            print("Estado efetivo: VERSAO_HISTORICA_EXISTENTE")
            print("Versoes inseridas: 0")
            print("Atuais inseridos/atualizados: 0")
            print("MODO: SEM ALTERACOES")
            return
        if estado == "CONFLITO_MESMA_DATA":
            # Preserva historico com estado explicito; registro ativo nao e alterado.
            print("AVISO: divergencia na mesma data; registro ativo sera preservado")

        observado = datetime.now(timezone.utc).isoformat()
        contagens_antes = {
            t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("contratacoes", "versoes", "importacoes")
        }
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                """INSERT OR IGNORE INTO contratacoes_detalhes_versoes
                   (id, payload_sha256, data_atualizacao_fonte,
                    observado_utc, payload_json, estado)
                   VALUES (?,?,?,?,?,?)""",
                (ident, sha, data_fonte, observado, payload,
                 estado if estado != "IDENTICO" else "PRIMEIRO_REGISTRO")
            )
            novas_versoes = db.execute("SELECT changes()").fetchone()[0]
            if estado in ("PRIMEIRO_REGISTRO", "MAIS_RECENTE"):
                db.execute(
                    """INSERT INTO contratacoes_detalhes
                       (id, codigo_sigilo, descricao_sigilo, data_atualizacao_fonte,
                        payload_sha256, payload_json, observado_utc)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                         codigo_sigilo=excluded.codigo_sigilo,
                         descricao_sigilo=excluded.descricao_sigilo,
                         data_atualizacao_fonte=excluded.data_atualizacao_fonte,
                         payload_sha256=excluded.payload_sha256,
                         payload_json=excluded.payload_json,
                         observado_utc=excluded.observado_utc
                       WHERE contratacoes_detalhes.data_atualizacao_fonte < excluded.data_atualizacao_fonte""",
                    (ident, codigo, documento.get("orcamentoSigilosoDescricao"),
                     data_fonte, sha, payload, observado)
                )
            novos_atuais = db.execute("SELECT changes()").fetchone()[0] if estado in ("PRIMEIRO_REGISTRO", "MAIS_RECENTE") else 0
            contagens_depois = {
                t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in contagens_antes
            }
            if contagens_antes != contagens_depois:
                raise ValueError("Contagens originais foram alteradas")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Chave estrangeira violada")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Integridade reprovada")
            db.commit()
        except Exception:
            db.rollback()
            raise
        print("Versoes inseridas:", novas_versoes)
        print("Atuais inseridos/atualizados:", novos_atuais)
        print("MODO: GRAVACAO CONCLUIDA")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banco", required=True)
    parser.add_argument("--arquivo", required=True)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    executar(args.banco, args.arquivo, args.aplicar)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERRO:", exc, file=sys.stderr)
        sys.exit(1)

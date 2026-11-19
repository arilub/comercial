import unittest
from datetime import date
from pncp_radar import build_url, pick, scan

class RadarTest(unittest.TestCase):
    def test_url(self):
        url = build_url(date(2026,11,18), date(2026,11,19), uf="CE")
        self.assertIn("codigoModalidadeContratacao=6", url)
        self.assertIn("dataInicial=20261118", url)
        self.assertIn("uf=CE", url)

    def test_normalizacao(self):
        row = pick({"numeroControlePNCP":"123-1-2","objetoCompra":"Óleo lubrificante",
            "orgaoEntidade":{"razaoSocial":"Órgão Exemplo"},
            "unidadeOrgao":{"ufSigla":"CE","municipioNome":"Fortaleza"}})
        self.assertEqual(row["id"], "123-1-2")
        self.assertEqual(row["uf"], "CE")

    def test_filtro_e_dedup(self):
        sample = {"data":[
            {"numeroControlePNCP":"a","objetoCompra":"Óleo lubrificante",
             "unidadeOrgao":{"ufSigla":"CE"}},
            {"numeroControlePNCP":"a","objetoCompra":"Óleo lubrificante",
             "unidadeOrgao":{"ufSigla":"CE"}},
            {"numeroControlePNCP":"b","objetoCompra":"Cimento",
             "unidadeOrgao":{"ufSigla":"CE"}}
        ]}
        rows, logs = scan(date(2026,11,18),date(2026,11,18),uf="CE",
                          keywords=["óleo"],getter=lambda _:sample,max_pages=1)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(logs),1)

if __name__ == "__main__":
    unittest.main()

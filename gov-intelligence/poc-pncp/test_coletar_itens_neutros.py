import unittest
from coletar_itens_neutros import collect_one, parse_id, url_itens

class ColetaItensTest(unittest.TestCase):
    def test_identificador(self):
        self.assertEqual(parse_id("10744098000145-1-000293/2026"), ("10744098000145", 2026, 293))

    def test_url_paginada(self):
        url = url_itens("10744098000145-1-000293/2026", 2, 50)
        self.assertIn("/compras/2026/293/itens?", url)
        self.assertIn("pagina=2", url)
        self.assertIn("tamanhoPagina=50", url)

    def test_neutralidade(self):
        def getter(_):
            return [{"numeroItem": 1, "descricao": "Drone", "valorTotal": 100}]
        rows, logs, state = collect_one("10744098000145-1-000293/2026",
                                        page_size=50, max_pages=1, getter=getter)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["aderencia"], "NEUTRO")
        self.assertEqual(rows[0]["classificacaoStatus"], "AGUARDANDO_VALIDACAO_GESTAO")
        self.assertEqual(len(logs), 1)

    def test_limite_paginacao(self):
        def getter(_):
            return [{"numeroItem": n} for n in range(1, 11)]
        _, _, state = collect_one("10744098000145-1-000293/2026",
                                   page_size=10, max_pages=1, getter=getter)
        self.assertEqual(state, "PARCIAL_LIMITE_PAGINAS")

if __name__ == "__main__":
    unittest.main()

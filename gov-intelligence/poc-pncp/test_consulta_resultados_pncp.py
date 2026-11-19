import unittest
from consulta_resultados_pncp import consultar, endpoint

class ResultadosTest(unittest.TestCase):
    def test_endpoint(self):
        self.assertIn("/compras/2025/22698/itens/1/resultados",
                      endpoint("07954480000179-1-022698/2025", "itens/1/resultados"))

    def test_neutro_e_resultado(self):
        def mock(url):
            if url.endswith("/resultados"):
                return [{"niFornecedor":"00000000000100","valorTotalHomologado":120}]
            return [{"numeroItem":1, "descricao":"Item teste","temResultado":True}]
        got = consultar("07954480000179-1-022698/2025", 1, getter=mock)
        self.assertEqual(got["itens"][0]["aderencia"],"NEUTRO")
        self.assertEqual(len(got["itens"][0]["resultados"]),1)

if __name__ == "__main__":
    unittest.main()

ACTIVE = "ACTIVE"

# CNPJs validos que a consulta simulada devolve como inelegiveis. Servem
# para os testes provarem que o cadastro so ativa quem a fonte aprova.
SIMULATED_INELIGIBLE_CNPJS = {
    "22333444000181": "SUSPENDED",
    "33444555000181": "INAPT",
    "44555666000181": "CLOSED",
}


class CnpjRegistryConnector:
    """Consulta simulada da situacao cadastral do CNPJ.

    A situacao do CNPJ nao pode vir do corpo da requisicao: quem cadastra
    mandaria ACTIVE e aprovaria a si mesmo. Ela vem de uma fonte oficial,
    aqui representada por este connector.

    No MVP nao existe Receita Federal para consultar, entao a resposta e
    local: CNPJs da tabela acima voltam inelegiveis e os demais voltam
    ACTIVE. Quando houver um mock ou servico real, este arquivo passa a
    herdar de RestConnector (como o bankslip_connector.py) e o controller
    nao muda.
    """

    def get_cnpj_status(self, cnpj: str) -> str:
        return SIMULATED_INELIGIBLE_CNPJS.get(cnpj, ACTIVE)

# Blindagem por camadas — o que o banco garante hoje

Documento de apoio ao [RFC](../rfc.md). Ele lista as proteções **implementadas e testadas**, camada por camada, com o lugar onde cada uma mora; depois, com a mesma franqueza, os **riscos aceitos** nesta entrega e o que fica para a evolução. Não substitui análise jurídica, regulatória, testes de segurança ou uma plataforma de PLD/FT.

## 1. O princípio: o cliente só informa a intenção

Quem chama a API informa o que quer fazer — tipo (PIX ou TED), valor e destino (chave PIX ou banco, agência e conta) — e mais nada. Tudo o que é verdade financeira é decidido no servidor: o saldo, a tarifa, a regra de preço aplicada, os dados do recebedor e o resultado.

- Os JSON Schemas de entrada usam `additionalProperties: false`. Um pedido que tenta informar `fee_cents`, saldo ou status é **recusado** com `400`, não ignorado (teste `test_refuses_invalid_request[client_informs_fee]`).
- Os objetos são montados campo a campo nos repositories; nenhum model recebe o JSON inteiro.
- Não existe rota que altere saldo, transação ou movimento diretamente. O saldo só muda por uma transação.

## 2. Responsabilidade de cada camada

| Camada | O que protege | Onde |
|---|---|---|
| `middlewares/` | Exige o `INTERNAL-TOKEN` em toda rota de negócio (`403` sem ele); cria o `x-request-id` e **saneia** o que vier de fora, contra injeção de linhas no log; abre e fecha a sessão do banco com rollback em erro | `internal_token.py`, `request_context.py`, `session_manager.py` |
| `schemas/` | Formato, tipos, tamanhos, enums, centavos inteiros de 1 a 100 bilhões; recusa campos desconhecidos | `src/schemas/*.json` |
| `controllers/` | Regras de negócio: documento válido, maioridade, idempotência, travas, tarifa, conta ativa, ordem do fluxo e commit | `client_controller.py`, `transaction_controller.py` |
| `repositories/` | Movimentos de saldo atômicos (`UPDATE … RETURNING`), `ON CONFLICT` nas chaves únicas, travas em ordem; chave pública em formato inválido vira "não encontrado", não erro de banco | `account_repository.py`, `transaction_repository.py` |
| `database.sql` | A última barreira: `CHECK`, `UNIQUE`, chaves estrangeiras e triggers (seção 5) | `database/database.sql` |
| `connectors/` | O Banco Central fake é chamado com tempo limite; sem resposta vira "indisponível"; a confirmação só vale se passar por um schema (`central_bank_confirmation.json`) | `central_bank_connector.py` |
| `dtos/` | Lista explícita de campos: nunca sai `id` interno nem `password_hash`; CPF sai mascarado (`***.***.***-25`) no cliente, no representante e no recebedor de um envio | `client_dto.py`, `transaction_dto.py` |
| `errors/` | Todo erro tem formato único e código `QIT…` próprio; nunca stack trace; erro inesperado responde `500` genérico | `base_error.py`, `custom_errors.py` |

## 3. O dinheiro

| Garantia | Como | Provado por |
|---|---|---|
| Saldo nunca negativo | Débito num único `UPDATE … WHERE balance_cents >= total RETURNING`; nenhuma linha afetada = saldo insuficiente. `CHECK (balance_cents >= 0)` como última barreira | `test_many_sends_spend_exactly_what_the_balance_allows` |
| Nenhuma atualização perdida | Nunca "ler o saldo, calcular e gravar": crédito e débito são `balance_cents ± x` no próprio `UPDATE` | `test_crossed_transfers_never_lose_money_nor_fail` |
| Sem deadlock em envios cruzados | Contas travadas com `SELECT … FOR UPDATE` sempre na ordem do `id` | idem (20 envios A→B e B→A simultâneos); falha por deadlock quando a ordem é quebrada de propósito |
| Duplo clique paga uma vez | Chave de idempotência única por conta de origem: conferida antes, **conferida de novo depois da trava** e garantida pelo `ON CONFLICT (source_account_id, idempotency_key)`. Mesmo pedido devolve a mesma transação (`200`); outro pedido com a mesma chave, `422` | `test_double_click_creates_a_single_transaction`, `test_double_click_reaches_the_central_bank_once` |
| Recusa não deixa rastro | Saldo insuficiente, conta inativa ou Banco Central sem confirmação: rollback; a chave e a cota continuam livres | `test_refused_send_does_not_spend_the_idempotency_key`, `test_refused_send_does_not_spend_quota` |
| Tarifa certa sob concorrência | A cota do mês é contada com a conta travada, na mesma transação do débito | `test_two_sends_at_the_quota_limit_are_never_both_free` |
| Envio para outro banco só se confirmado | Síncrono: com a conta travada e o valor debitado, pergunta ao Banco Central e espera até 5 s; só grava com a confirmação | `TestExternalPix`, `TestExternalTed` |
| Recebimento creditado uma vez | Referência única por tipo e banco de origem, resolvida pelo `ON CONFLICT` | `test_concurrent_repeated_notices_credit_only_once` |
| Dinheiro não nasce nem some | Transação, movimentos e saldos no mesmo commit; soma dos saldos = recebido − enviado para fora − tarifas | `test_balances_equal_received_minus_sent_out_minus_fees` |
| Extrato prova o saldo | Cada movimento guarda o saldo depois dele, vindo do `RETURNING`; as linhas encadeiam e somam o saldo | `test_lines_chain_and_add_up_to_the_balance` |

## 4. Cadastro e dados pessoais

- **Documento válido:** CPF e CNPJ (numérico e alfanumérico) conferidos pelos dígitos verificadores; guardados sem máscara e em maiúsculas, para que "123.456.789-09" e "12345678909" sejam o mesmo cadastro.
- **Situação do CNPJ** vem de uma consulta (simulada por connector), nunca do corpo da requisição — quem cadastra não pode se aprovar.
- **Maioridade** calculada no dia de Brasília, para PF e para o representante.
- **E-mail único no banco inteiro**, entre clientes e representantes, garantido pela tabela `registered_email` mesmo com cadastros simultâneos (`test_client_concurrency.py`).
- **Senha** guardada só como hash Argon2id com salt aleatório (`utils/password.py`); nunca sai em resposta.
- **Mensagens de erro** não repetem CPF, CNPJ, e-mail nem senha; o `400` de schema não ecoa o valor recebido.
- **Log:** registra método, caminho e status, sem corpo nem cabeçalhos; um `IntegrityError` inesperado registra só o nome da constraint, não os dados do cadastro.
- **Imagem Docker** roda com usuário não root; dependências com versão fixa; `.env` fora do Git.

## 5. Barreiras no banco de dados, mesmo se o código errar

| Tabela | Barreira |
|---|---|
| `transaction` | Nunca editada nem apagada (trigger append-only para `UPDATE` e `DELETE`; `TRUNCATE` recusado). Valor entre 1 e 100 bilhões de centavos; tarifa ≥ 0; origem diferente do destino; campos coerentes com entrada e saída; documento da outra parte com formato válido |
| `account_movement` | Nunca editado nem apagado; valor sempre positivo; saldo depois ≥ 0; só `PRINCIPAL` ou `FEE` |
| `account` | Nunca apagada; só saldo e status mudam (agência, número, dígito e dono são fixos); saldo ≥ 0; uma conta por cliente; número único |
| `tariff_rule` | Nunca editada nem apagada; **só envio de PJ pode ter preço** (`ck_tariff_rule_only_pj_sends_pay`): uma regra que cobre PF ou recebimento é recusada |
| `client` e `legal_representative` | Documento e e-mail únicos; campos de PF e de PJ coerentes com o tipo; e-mail em minúsculas; representante só para PJ; toda PJ com pelo menos um representante (verificado no commit) |
| `registered_email` | E-mail único entre clientes e representantes; o e-mail do cadastro não muda |

Toda constraint tem nome, e as violações esperadas viram erro de negócio com código próprio (por exemplo, e-mail repetido → `409 QIT002004`).

## 6. Riscos aceitos nesta entrega

Escolhas conscientes do escopo "make it simple", registradas para não parecerem esquecimento.

| Risco | Por que existe | O que reduz hoje |
|---|---|---|
| **Sem login (R8 / IDOR):** quem tem o `INTERNAL-TOKEN` consulta e movimenta qualquer conta | Login e autorização por usuário ficaram fora da fase 1 | Chaves públicas em UUID (não enumeráveis); o token protege a API como um todo |
| **Token único e compartilhado** | Padrão do repositório-base para chamadas internas | Valor vem do ambiente; padrão só para uso local |
| **Webhook do Banco Central autenticado só pelo token** (sem assinatura nem janela de tempo) | O Banco Central é simulado | Referência única impede crédito repetido; schema estrito |
| **Sem limite de requisições** | Fora do escopo | Paginação com teto de 100; timeout no connector |
| **Confirmação perdida:** o Banco Central confirma e a resposta não chega | Envio síncrono sem reconciliação | O pedido é recusado aqui e pode ser refeito; risco registrado em `04-transacao.md` |
| **A tarifa sai do cliente e não entra em conta nenhuma** | A conta de receita do banco foi adiada | A tarifa fica registrada na transação e no extrato |
| **Cadastro protegido só pela API:** o banco aceitaria apagar cliente ou mudar documento | Não há rota para isso; a imutabilidade no banco foi priorizada para o dinheiro | Nenhuma rota de edição ou exclusão de cadastro |
| **Documento do pagador e chave PIX (quando é CPF) saem inteiros** nas respostas de recebimento e envio | São dados que quem chama já informou | CPF de clientes e recebedores sai mascarado |
| **Configuração de desenvolvimento:** senhas padrão, porta do banco publicada, `--reload` | Projeto local de estudo | Tudo vem de variável de ambiente; trocar não exige mudar código |
| **Sem trilha de auditoria separada** | Fora do escopo | `x-request-id` em toda resposta e no log; transações e movimentos imutáveis |

## 7. Evolução (fora da fase 1)

O desenho da versão 6 do RFC continua sendo o caminho para produção, nesta ordem:

1. **Login e autorização por objeto:** sessão curta ligada à PF ou ao representante; toda busca de conta, extrato e transação restrita ao cliente da sessão, com `404` para recurso alheio (R8); a transação passa a guardar quem pediu (ACE-07).
2. **Autorização do envio com MFA vinculada ao valor e ao destino** ("o que você vê é o que você assina") e limites por janela de tempo.
3. **Antifraude explicável** (valor, velocidade, destinatário novo, mudanças recentes) com a decisão e o motivo persistidos.
4. **Onboarding com fonte oficial:** situação cadastral real, quadro de sócios, prova de vida e confirmação de e-mail e telefone.
5. **Webhook assinado** (ou mTLS) com proteção contra replay; envio externo assíncrono com reconciliação e estorno aditivo.
6. **Operação:** limite de requisições, segredos em cofre, privilégio mínimo no banco (a aplicação sem `UPDATE`/`DELETE` nas tabelas financeiras) e Row-Level Security como segunda barreira.

## 8. Fontes de referência

- [Resolução CMN nº 4.753 — identificação e qualificação de titulares e representantes](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50847/Res_4753_v6_L.pdf)
- [Receita Federal — CNPJ alfanumérico e cálculo dos dígitos verificadores](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cnpj-alfanumerico)
- [OWASP Password Storage — Argon2id e salt](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP API Security Top 10 2023](https://api-security.owasp.org/editions/2023/en/0x00-header/)
- [OWASP Mass Assignment — allowlist e schemas separados](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [OWASP Transaction Authorization — vinculação de valor e destino à autorização](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
- [PostgreSQL — constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [PostgreSQL — Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

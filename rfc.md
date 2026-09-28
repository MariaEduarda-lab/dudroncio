# RFC — Conta transacional PJ com PIX e TED

| | |
|---|---|
| **Time** | <preencher nomes do time> |
| **Data** | 27/09/2026 |
| **Versão** | 3 — modelo PJ e blindagem transacional |

## Contextualização

### Entendendo o problema

O sistema oferece o cadastro de clientes pessoa jurídica, a abertura de conta vinculada ao cliente, a consulta de saldo e a movimentação por PIX ou TED. Cada movimentação pode gerar tarifa e deve aparecer em um extrato paginado. A principal garantia é que dinheiro não seja criado, perdido, cobrado duas vezes ou gasto após o saldo acabar, inclusive quando duas requisições chegam juntas ou uma requisição é reenviada. O histórico precisa explicar o saldo atual sem permitir que uma alteração apague o que aconteceu. Também é necessário barrar clientes, contas e transações incompatíveis com as regras de cadastro e de risco. Ficam fora desta versão cartões, boletos, saques, crédito, juros, câmbio, conta conjunta, integração real com SPI/STR e uma plataforma completa de PLD/FT; os pontos de integração externa serão representados por contratos e estados.

### Explicando a solução de forma macro

O modelo inicialmente levantado pelo time foi: `Cliente(id, CNPJ, email, senha, endereço, número de contato, token)`; `Conta(id, cliente_id, número da conta, status, timestamp)`; `Transação(id, conta_id, timestamp, status, valor, destino, tipo PIX/TED, entrada/saída, tarifa_cobrada)`; `Extrato(id, transação_id, cobertura_temporal)`; `Tarifa(id, tarifa_pix, tarifa_ted, transação_id)`; e `Banco(id, clientes_id, CNPJ, balanço_financeiro, local_de_depósito)`.

A proposta final mantém Cliente, Conta, Transação e Tarifa, acrescenta o representante legal da empresa e separa a operação financeira dos movimentos imutáveis que alteram uma conta. O saldo corrente fica em `account` para consulta rápida; cada débito, crédito, tarifa ou estorno fica em `account_movement`, permitindo reconstrução e conciliação. A mesma transação ACID trava a conta, grava os movimentos e atualiza o saldo. O extrato passa a ser uma consulta por período sobre esses movimentos, não uma entidade. A tarifa vira uma regra com vigência, e a transação guarda uma cópia do valor efetivamente cobrado.

Para o projeto, os dados básicos da empresa são CNPJ, razão social, nome fantasia opcional, situação cadastral do CNPJ, atividade principal, faturamento mensal informado, contato e endereço. Também se identifica ao menos um representante legal com CPF, nome, nascimento, contato e função. Esta é uma modelagem acadêmica mínima, não uma lista universal de conformidade: a [Resolução CMN nº 4.753](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50847/Res_4753_v6_L.pdf) exige procedimentos para identificar e qualificar o titular e seus representantes, validar a autenticidade e conhecer perfil de risco/capacidade econômico-financeira; a Receita também disponibiliza situação cadastral e QSA na [consulta oficial do CNPJ](https://www.gov.br/pt-br/servicos/consultar-cadastro-nacional-de-pessoas-juridicas).

`financial_transaction` representa a operação única e seu comprovante. `account_movement` representa cada efeito no saldo e cada linha do extrato: um PIX de R$ 100,00 com tarifa de R$ 2,00 produz uma transação, um movimento de débito de 10.000 centavos e outro de tarifa de 200 centavos. `account_status_history` não cria outra conta: conserva quando e por que a única conta daquele CNPJ mudou de estado. `transaction_risk_analysis` conserva a decisão antifraude e um motivo legível. Entidades expostas pela API têm `..._key`; tabelas internas de detalhe usam somente `id`.

**Como a entrega de extrato é atendida:** o extrato é a representação retornada por `GET /accounts/{account_key}/transactions`, não uma tabela adicional. A API recebe período e paginação, busca os `account_movement` daquela conta, associa cada movimento à sua `financial_transaction` e devolve saldo inicial, créditos, débitos, tarifas, estornos e saldo final. Não persistir uma cópia do extrato evita divergência quando uma transação é estornada. O índice `(account_id, created_at, id)` mantém a consulta eficiente e a ordenação estável.

- **Manter exatamente o modelo inicial** — descartado porque `extrato` duplicaria dados, a tarifa ficaria invertida em relação à transação, `destino` seria texto sem estrutura e não haveria trilha capaz de reconciliar o saldo. Ganharia se o objetivo fosse apenas uma demonstração descartável, sem concorrência ou auditoria.
- **Calcular sempre o saldo pela soma das transações** — descartado porque encarece toda consulta e torna bloqueio de saldo concorrente mais difícil. Ganharia em um livro-razão completo, com infraestrutura de ledger e projeções assíncronas.
- **Guardar somente o saldo na conta** — descartado porque é rápido, mas não explica como o saldo foi formado nem produz um extrato auditável. Ganharia se não existisse exigência de histórico financeiro.
- **Criar tabelas diferentes para PIX e TED** — descartado porque duplica regras e obriga o extrato a unir fontes. Ganharia se os dois meios tivessem ciclos, campos e times completamente independentes.
- **Criar a entidade `bank`** — descartado porque há um único banco, que é o próprio sistema, e `clientes_id` criaria uma relação redundante. Ganharia em uma plataforma multi-instituição; nesse caso, a entidade representaria instituições participantes, não balanço financeiro mutável.

As premissas desta versão são: clientes são pessoas jurídicas identificadas por CNPJ; cada cliente pode ter uma conta no MVP; valores são inteiros em centavos; chaves UUID são expostas pela API e IDs inteiros ficam internos; senha nunca é salva em texto puro, apenas como `password_hash`; token de acesso não é atributo permanente do cliente e, se autenticação entrar no escopo, deverá ser expirável e armazenado somente como hash. Dados de destinatário externo são fotografados na transação para que mudanças posteriores não alterem o comprovante.

Os controles de identidade, autenticação, autorização, concorrência, antifraude e auditoria estão detalhados no [documento de blindagem por camadas](docs/blindagem.md).

## Implementação

### Rotas

| Método | Caminho | O que faz | Entrada (campos que importam) | Saídas (status e quando) |
|---|---|---|---|---|
| `POST` | `/clients` | Cadastra cliente PJ e representante principal | dados da empresa; objeto `legal_representative` com CPF, nome, contato, função e senha | `201` com `client_key`; `400` corpo inválido; `422` CNPJ inválido; `409` CNPJ ou e-mail já cadastrado. Não é idempotente; unicidade impede duplicata, mas a repetição recebe conflito. |
| `GET` | `/clients/{client_key}` | Consulta cliente | UUID no caminho | `200`; `404` chave inexistente. Idempotente por ser somente leitura. |
| `POST` | `/clients/{client_key}/accounts` | Abre conta | tipo da conta; `client_key` no caminho | `201` com `account_key`; `400` corpo inválido; `404` cliente inexistente; `409` cliente bloqueado ou já possui a conta permitida. Não é idempotente nesta versão. |
| `GET` | `/accounts/{account_key}` | Consulta conta e saldo | UUID no caminho | `200`; `404` chave inexistente. Idempotente por ser somente leitura. |
| `PATCH` | `/accounts/{account_key}` | Bloqueia, reativa ou encerra conta | `status`, `reason` | `200`; `400` corpo inválido; `404` conta inexistente; `409` transição de estado proibida. Idempotente quando repete o mesmo estado e motivo. |
| `POST` | `/accounts/{account_key}/transactions` | Cria intenção PIX/TED com snapshot imutável | cabeçalho `Idempotency-Key`; `type`, `amount_cents`, identificador do destino | `201` em `AWAITING_AUTHORIZATION`; `200` ao repetir a mesma chave e corpo; `400` corpo/campo proibido; `404` conta inexistente/alheia; `409` chave reutilizada com outro corpo ou conta inativa; `422` destino, limite ou risco recusado. Idempotente por `(account_id, idempotency_key)`. |
| `POST` | `/webhooks/transactions` | Registra PIX ou TED de entrada confirmado pela rede | autenticação interna; `external_reference`, `type`, `amount_cents`, conta de destino e remetente | `201` crédito criado; `200` ao repetir a mesma referência e corpo; `400` corpo inválido; `404` conta destino inexistente; `409` referência repetida com conteúdo diferente ou conta encerrada. Idempotente pela unicidade de `external_reference`. |
| `POST` | `/transactions/{transaction_key}/authorizations` | Confirma exatamente destino, valor e tarifa do snapshot | prova de autenticação de uso único; nenhum dado financeiro | `200/202` autorizada ou em processamento; `400` campo financeiro enviado; `401` prova inválida; `404` transação inexistente/alheia; `409` expirada, já autorizada ou fingerprint divergente; `422` risco/saldo/limite recusado. Idempotente pela transação e desafio de uso único. |
| `GET` | `/transactions/{transaction_key}` | Consulta estado e comprovante | UUID no caminho | `200`; `404` chave inexistente ou alheia. Idempotente por ser somente leitura. |
| `GET` | `/accounts/{account_key}/transactions?created_from=...&created_to=...&limit=...&page=...` | Entrega o extrato financeiro calculado a partir dos movimentos | período e paginação na query string | `200` com saldos inicial/final e lançamentos; `400` período/paginação inválidos; `404` conta inexistente. Idempotente por ser somente leitura. |

### Banco de Dados (Somente diagrama)

```mermaid
erDiagram
    LEGAL_ENTITY_CLIENT ||--|{ LEGAL_REPRESENTATIVE : "autoriza"
    LEGAL_ENTITY_CLIENT ||--o| ACCOUNT : "possui no MVP"
    ACCOUNT ||--o{ ACCOUNT_STATUS_HISTORY : "tem historico"
    ACCOUNT o|--o{ FINANCIAL_TRANSACTION : "origina"
    ACCOUNT o|--o{ FINANCIAL_TRANSACTION : "recebe"
    ACCOUNT ||--o{ ACCOUNT_MOVEMENT : "movimentos formam extrato"
    FINANCIAL_TRANSACTION ||--|{ ACCOUNT_MOVEMENT : "gera"
    TARIFF_RULE o|--o{ FINANCIAL_TRANSACTION : "precifica quando aplicavel"
    FINANCIAL_TRANSACTION ||--o| TRANSACTION_RISK_ANALYSIS : "e analisada"
    LEGAL_REPRESENTATIVE ||--o{ FINANCIAL_TRANSACTION : "solicita e autoriza"

    LEGAL_ENTITY_CLIENT {
        bigint id PK "interno"
        uuid client_key UK "publico"
        char cnpj UK "14 caracteres normalizados"
        varchar corporate_name "razao social"
        varchar trade_name "nome fantasia opcional"
        varchar legal_nature_code "natureza juridica"
        date incorporation_date "data de constituicao"
        varchar cnpj_status "situacao na Receita"
        varchar primary_activity_code "CNAE principal"
        bigint declared_monthly_revenue_cents "faturamento informado"
        varchar email
        varchar phone
        char postal_code
        varchar street
        varchar address_number
        varchar address_complement "opcional"
        varchar district
        varchar city
        char state
        char country_code "BR"
        varchar status "PENDING ACTIVE BLOCKED CLOSED"
        timestamptz created_at
        timestamptz updated_at
    }

    LEGAL_REPRESENTATIVE {
        bigint id PK "interno"
        uuid representative_key UK "publico"
        bigint client_id FK
        char cpf "unico por cliente e protegido"
        varchar full_name
        date birth_date
        varchar email
        varchar phone
        varchar role "socio administrador procurador"
        boolean is_primary
        varchar password_hash "nunca senha pura"
        varchar status "PENDING ACTIVE BLOCKED"
        timestamptz created_at
        timestamptz updated_at
    }

    ACCOUNT {
        bigint id PK "interno"
        uuid account_key UK "publico"
        bigint client_id FK, UK "uma conta por CNPJ"
        varchar branch_number "agencia do nosso banco"
        varchar account_number UK
        varchar account_check_digit
        bigint balance_cents "saldo em centavos"
        varchar status "CREATED ACTIVE BLOCKED CLOSED"
        timestamptz created_at
        timestamptz updated_at
    }

    ACCOUNT_STATUS_HISTORY {
        bigint id PK
        bigint account_id FK
        varchar from_status
        varchar to_status
        varchar reason
        bigint changed_by_representative_id FK "nulo se alterado pelo sistema"
        timestamptz created_at
    }

    FINANCIAL_TRANSACTION {
        bigint id PK "interno"
        uuid transaction_key UK "publico e comprovante"
        bigint origin_account_id FK "nulo na entrada externa"
        bigint destination_account_id FK "nulo na saida externa"
        bigint tariff_rule_id FK
        bigint requested_by_representative_id FK
        bigint authorized_by_representative_id FK "nulo ate autorizacao"
        uuid idempotency_key "evita envio duplicado"
        varchar external_reference UK "id recebido da rede"
        varchar request_fingerprint "confere repeticao"
        varchar authorization_fingerprint "vincula destino valor e tarifa"
        timestamptz authorization_expires_at "validade do desafio"
        varchar authorization_method "nulo ate autorizacao"
        varchar type "PIX TED"
        bigint amount_cents "10000 representa R 100"
        bigint fee_cents "tarifa cobrada nesta operacao"
        varchar status "PENDING AWAITING_AUTHORIZATION PROCESSING COMPLETED FAILED REVERSED"
        varchar beneficiary_name
        varchar beneficiary_document
        varchar destination_pix_key "somente PIX"
        varchar destination_bank_code "somente TED"
        varchar destination_branch "agencia destino da TED"
        varchar destination_account "conta destino da TED"
        timestamptz created_at
        timestamptz updated_at
        timestamptz authorized_at "opcional"
        timestamptz completed_at "opcional"
    }

    ACCOUNT_MOVEMENT {
        bigint id PK
        bigint account_id FK
        bigint transaction_id FK
        varchar direction "DEBIT CREDIT"
        varchar movement_type "PRINCIPAL FEE REVERSAL"
        bigint amount_cents "valor do movimento"
        bigint balance_after_cents "saldo apos movimento"
        timestamptz created_at "indice com account_id e id"
    }

    TARIFF_RULE {
        bigint id PK
        varchar transaction_type "PIX TED"
        bigint fixed_amount_cents
        integer percentage_basis_points
        bigint minimum_amount_cents
        bigint maximum_amount_cents
        timestamptz valid_from
        timestamptz valid_until "opcional"
        boolean active
        timestamptz created_at
        timestamptz updated_at
    }

    TRANSACTION_RISK_ANALYSIS {
        bigint id PK
        bigint transaction_id FK, UK "uma analise por transacao"
        varchar decision "APPROVED REVIEW BLOCKED"
        varchar reason_code "ex NEW_BENEFICIARY_HIGH_VALUE"
        varchar reason_description
        timestamptz analyzed_at
    }
```

### Fluxos

**Cadastro de cliente — caminho feliz**

1. O schema valida formato e campos obrigatórios; o domínio normaliza e valida CNPJ e e-mail.
2. O serviço verifica as restrições únicas, transforma a senha do representante com algoritmo de hash adequado e cria cliente e representante em `PENDING`.
3. A política cadastral aprova o cliente, registra `ACTIVE` e responde `201` com `client_key`, nunca com IDs internos, CPF completo ou `password_hash`.

**Cadastro de cliente — falha: identidade repetida ou inválida**

1. CNPJ inválido recebe `422`; CNPJ/e-mail que viola unicidade recebe `409`.
2. A operação é revertida por inteiro e a resposta usa o corpo padrão de erro (`title`, `description`, `translation`, `code`).

**Abertura de conta — caminho feliz**

1. O serviço busca o cliente por `client_key`, confirma `ACTIVE` e verifica o limite de uma conta no MVP.
2. Cria a conta com saldo zero e estado `CREATED`, grava a primeira linha do histórico de status e então a ativa.
3. A transação confirma as duas gravações e responde `201` com `account_key`.

**Abertura de conta — falha: cliente inelegível**

1. Cliente inexistente recebe `404`; cliente bloqueado ou com conta já aberta recebe `409`.
2. Nenhuma conta nem evento parcial permanece no banco.

**PIX/TED de saída — caminho feliz**

1. O serviço autoriza o representante na conta e procura `(account_id, idempotency_key)`. Se já existir com o mesmo `request_fingerprint`, devolve o resultado anterior; com corpo diferente, responde `409`.
2. Valida conta ativa, valor e limites, resolve o favorecido e calcula a tarifa no servidor. Grava origem, destino resolvido, tipo, valor, tarifa, solicitante e expiração como snapshot imutável em `AWAITING_AUTHORIZATION`.
3. A análise de risco verifica valor, frequência, horário, dispositivo, destinatário novo, tentativas e alterações cadastrais. `BLOCKED` recusa; `REVIEW` não movimenta; `APPROVED` permite solicitar autenticação adicional.
4. O servidor mostra favorecido, documento mascarado, valor e tarifa e gera desafio de uso único vinculado ao `authorization_fingerprint`. A confirmação recebe somente a prova de autenticação; qualquer tentativa de reenviar destino, valor, tarifa ou origem recebe `400`.
5. Ao confirmar, o servidor relê o snapshot e confere fingerprint, expiração, sessão, titularidade e estado. Mudança exige cancelar e criar outra transação; não existe `PATCH`.
6. O banco trava a conta com `SELECT ... FOR UPDATE`, relê o saldo e verifica `saldo >= valor + tarifa`.
7. Na mesma transação ACID, marca `PROCESSING`, cria movimentos `PRINCIPAL` e `FEE` e atualiza o saldo. Qualquer falha causa rollback.
8. No MVP, a confirmação externa é simulada. Em integração real, sucesso vira `COMPLETED`, falha definitiva gera `REVERSAL` e timeout permanece inconclusivo para consulta e reconciliação.

**PIX/TED de saída — falha: concorrência, risco ou indisponibilidade**

1. Duas solicitações para a mesma conta esperam a mesma trava; a segunda relê o saldo depois do commit da primeira e recebe `422` se o total já não couber.
2. Reenvio com a mesma chave nunca cria novo débito. Decisão `BLOCKED` registra os motivos e responde `422`, sem lançamento financeiro.
3. Se o serviço externo falhar antes da confirmação, a operação não é marcada como concluída. O estado permanece rastreável (`PENDING`/`FAILED`) e uma retentativa usa a mesma chave; estorno, quando necessário, cria lançamentos inversos e nunca apaga o original.

**PIX/TED de entrada — caminho feliz**

1. A rota interna autentica a origem, valida a referência única da rede e localiza a conta de destino ativa.
2. Trava a conta e, no mesmo commit, cria a transação concluída, o lançamento `CREDIT` e o novo saldo.
3. A repetição da mesma referência e conteúdo devolve o resultado existente, sem creditar novamente.

**PIX/TED de entrada — falha: evento repetido ou conta inválida**

1. Referência já usada com conteúdo diferente recebe `409`; conta inexistente recebe `404`; conta encerrada recebe `409`.
2. Nenhum crédito parcial permanece e a tentativa entra no log de segurança para investigação.

**Consulta de extrato — caminho feliz**

1. O serviço valida conta, período e paginação e consulta `account_movement` pelo índice `(account_id, created_at, id)`.
2. Associa cada movimento à `financial_transaction` para obter PIX/TED, contraparte, estado e `transaction_key`.
3. Retorna saldo inicial, lista ordenada de créditos, débitos, tarifas e estornos, e saldo final. Portanto, o extrato é produzido sob demanda sem duplicar os movimentos em outra tabela.

**Consulta de extrato — falha: período inválido**

1. Período invertido, excessivo ou paginação fora do contrato recebe `400`; conta inexistente recebe `404`.
2. A leitura não altera estado e nunca depende de uma tabela de extrato previamente materializada.

> ## Principal desafio
>
> - **Qual é:** impedir débito duplicado ou saldo negativo sem perder auditabilidade, mesmo com concorrência, retentativas e avaliação antifraude.
> - **Por que é difícil:** saldo rápido favorece uma coluna mutável, extrato confiável favorece eventos imutáveis, e chamadas externas podem terminar sem uma resposta conclusiva.
> - **Como o desenho resolve:** chave de idempotência com impressão do corpo, trava pessimista da conta, atualização do saldo e lançamentos no mesmo commit, histórico sem `DELETE`/`UPDATE` financeiro, estados explícitos e avaliação de risco persistida. A primeira implementação deve provar essas garantias com testes de requisições simultâneas, repetição da mesma chave, rollback após falha e reconciliação entre saldo e lançamentos.

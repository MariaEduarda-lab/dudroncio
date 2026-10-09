# Dudroncio — banco PF/PJ com Pix, TED e tarifas

Protótipo de banco do Bootcamp QI Tech 2026: uma API REST em **Python + FastAPI**, com
**PostgreSQL**, rodando em **Docker**. Ele faz cinco coisas:

1. **Cliente:** cadastro de pessoa física (CPF) e jurídica (CNPJ, numérico ou alfanumérico,
   com representante legal).
2. **Conta:** uma por cliente, com número sorteado, dígito verificador e status
   (`ACTIVE`, `BLOCKED`, `CLOSED`).
3. **Transação:** só Pix e TED. Recebimentos vindos de outros bancos, envios entre clientes
   do banco e envios para outros bancos, todos síncronos.
4. **Tarifa:** PF não paga. PJ tem 20 Pix e 2 TED grátis por mês e depois paga R$ 0,99 por
   Pix e R$ 4,99 por TED. Receber é sempre grátis.
5. **Extrato:** paginado, do mais recente ao mais antigo, com a tarifa em linha separada.

O desenho, as decisões e as alternativas descartadas estão no [RFC](rfc.md).

---

## 1. O que você precisa ter instalado

| O quê | Para quê | Como conferir |
|---|---|---|
| **Docker** com Compose v2 (Docker Desktop no Mac/Windows) | sobe a API, o banco e o Banco Central fake | `docker compose version` |
| **Git** | baixar o projeto | `git --version` |
| **Python 3.11, 3.12 ou 3.13** | rodar os testes (seção 3) | `python3 --version` |

> Python 3.14 ainda não serve: algumas dependências fixadas no `requirements.txt` não têm
> versão para ele.

---

## 2. Subindo o projeto

```bash
docker compose up -d --wait
```

Não precisa criar nem copiar arquivo antes: toda configuração tem valor padrão no
`docker-compose.yml`. O `--wait` só devolve o terminal quando tudo estiver respondendo. Na
primeira vez o Docker baixa as imagens (é preciso internet) e demora alguns minutos.

Sobem três serviços:

| Serviço | O que é | Porta na sua máquina |
|---|---|---|
| `api` | a API do banco | `3000` |
| `db` | o PostgreSQL, já com as tabelas e a tabela de tarifas | `5432` |
| `mockserver` | o **Banco Central fake**, que confirma ou recusa os envios para outros bancos | `1080` |

Confira: http://localhost:3000 responde `{"service":"bootcamp-api","id":"8"}`.

Para desligar: `docker compose down`. Para recomeçar com o banco vazio:
`docker compose down -v && docker compose up -d --wait`.

---

## 3. Rodando os testes

Os testes rodam **na sua máquina**, contra a API que está de pé no Docker.

**Uma vez só:**

```bash
python3 -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

**Toda vez, com o projeto de pé (seção 2):**

```bash
pytest
```

```
============================= 288 passed in 22s ==============================
```

Os testes são **black box**: fazem requisições HTTP de verdade, como um cliente faria, e não
importam nada de `src/` nem leem o banco. Cada teste cria os próprios clientes, com documentos
novos, então dá para rodar a suíte várias vezes seguidas sem zerar o banco. Nos envios para
outros bancos, o teste faz o papel do Banco Central: diz ao Mockserver se ele deve confirmar,
recusar ou demorar (`tests/utils/central_bank_mock.py`). Testes unitários existem só para
cálculos isolados: dígito da conta e tarifa.

| Pasta | O que cobre |
|---|---|
| `tests/integration/client/` | cadastro PF/PJ, documento e e-mail únicos (inclusive com pedidos simultâneos) |
| `tests/integration/account/` | abertura de conta e mudança de status |
| `tests/integration/transaction/` | recebimento de TED e Pix, envio interno e externo, tarifa, idempotência e concorrência (20 transferências cruzadas, duplo clique, disputa pela última vaga grátis, conservação do dinheiro) |
| `tests/integration/statement/` | extrato, paginação e a soma das linhas igual ao saldo |
| `tests/unit/` | dígito verificador e cálculo da tarifa |

Os testes leem o seu `.env` (seção 7): se você trocar uma porta ali, eles passam a usar a
porta nova.

---

## 4. Um passeio pela API

Todas as rotas (menos `/` e `/health_check`) exigem o cabeçalho `INTERNAL-TOKEN`. Os comandos
abaixo funcionam no terminal do Mac e do Linux; no Windows, use o **Git Bash**. As chaves
(`client_key`, `account_key`) nascem diferentes a cada vez: troque as dos exemplos pelas suas.

**Cadastrar uma PF:**

```bash
curl -X POST http://localhost:3000/clients \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -d '{"person_type": "PF", "document_number": "529.982.247-25", "full_name": "Ana Souza",
       "birthdate": "1995-08-21", "password": "senha-forte-123", "monthly_income_cents": 750000,
       "email": "ana.souza@exemplo.com.br", "phone_number": "+5511977777777",
       "address": {"street": "Avenida Paulista", "number": "1000", "neighborhood": "Bela Vista",
                   "city": "Sao Paulo", "state": "SP", "postal_code": "01310100", "country": "BR"}}'
```

```json
{"client_key":"fb8bc4b1-a521-43c9-abbb-8df4c56a384f"}
```

Mande o mesmo CPF de novo (com ou sem pontuação) e a API recusa com `409`:

```json
{"title":"CPF already registered","description":"There is already a client with this CPF.","translation":"Já existe um cliente cadastrado com este CPF.","code":"QIT002010"}
```

**Cadastrar uma PJ** (com o representante legal, que é cadastrado junto):

```bash
curl -X POST http://localhost:3000/clients \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -d '{"person_type": "PJ", "document_number": "11.222.333/0001-81",
       "legal_name": "Pedro Farinhas Distribuidora Ltda", "trade_name": "Farinhas do Pedro",
       "primary_activity": "Comercio atacadista de alimentos", "monthly_income_cents": 5000000,
       "email": "financeiro@farinhas.com.br", "phone_number": "+5511999999999",
       "address": {"street": "Rua das Flores", "number": "10", "neighborhood": "Centro",
                   "city": "Sao Paulo", "state": "SP", "postal_code": "01001000", "country": "BR"},
       "legal_representative": {"cpf": "390.533.447-05", "full_name": "Pedro Farinhas",
                                "birthdate": "1980-03-10", "email": "pedro@farinhas.com.br",
                                "phone_number": "+5511988888888", "role": "SOCIO_ADMINISTRADOR",
                                "password": "outra-senha-forte"}}'
```

**Abrir a conta de cada um** e consultar:

```bash
curl -X POST http://localhost:3000/clients/<client_key>/accounts \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" -d '{}'

curl http://localhost:3000/accounts/<account_key> -H "INTERNAL-TOKEN: default_token"
```

```json
{"account_key":"e864dd8e-2245-42ac-b3ce-17dc9b83525c","client_key":"cd50e6e6-f1ed-416b-bbec-365e3925b95b","branch":"0001","account_number":"19865166","check_digit":"0","balance_cents":0,"status":"ACTIVE","status_reason":null,"created_at":"...","updated_at":"..."}
```

**Receber uma TED de outro banco.** É o Banco Central quem avisa; aqui você faz o papel dele.
Use a agência, o número e o dígito da conta da PJ:

```bash
curl -X POST http://localhost:3000/webhook/central_bank/teds \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -d '{"external_id": "TED-0001", "amount_cents": 200000,
       "recipient": {"branch": "0001", "account_number": "19865166", "check_digit": "0"},
       "payer": {"name": "Carlos Lima", "document": "11144477735", "bank_code": "237",
                 "branch": "1234", "account_number": "0098765"}}'
```

O mesmo aviso, mandado de novo, devolve a mesma transação (`200`) sem creditar outra vez.

**Mandar um Pix da PJ para a Ana**, pela chave Pix (o e-mail dela). O cabeçalho
`Idempotency-Key` é obrigatório:

```bash
curl -X POST http://localhost:3000/accounts/<account_key da PJ>/transactions \
  -H "INTERNAL-TOKEN: default_token" -H "Content-Type: application/json" \
  -H "Idempotency-Key: pix-ana-0001" \
  -d '{"type": "PIX", "amount_cents": 50000, "pix_key": "ana.souza@exemplo.com.br"}'
```

```json
{"transaction_key":"837bf409-a3db-412f-9364-de03daafedc8","type":"PIX","direction":"OUT","amount_cents":50000,"fee_cents":0,"created_at":"...","account_key":"e864dd8e-...","recipient":{"name":"Ana Souza","document":"***.***.***-25","bank_code":"999","branch":"0001","account_number":"30048258-2"},"pix_key":"ana.souza@exemplo.com.br"}
```

- **Mandou de novo com a mesma `Idempotency-Key`?** Volta a mesma transação, com `200`, e o
  dinheiro não sai duas vezes. É o que protege o duplo clique.
- **`fee_cents` é 0** porque é um dos 20 Pix grátis do mês da PJ. A partir do 21º, sai
  R$ 0,99 a mais da conta dela, e a Ana continua recebendo o valor cheio.
- **Chave Pix que não é de um cliente nosso** vai para o Banco Central fake. Sem uma resposta
  combinada no Mockserver, ele responde "não encontrado", e a API devolve `404`.
- **Sem saldo para valor mais tarifa:** `422` com o código `QIT004006`, e nada muda.

**Ver o extrato** (mais recente primeiro):

```bash
curl "http://localhost:3000/accounts/<account_key da PJ>/statement?limit=2" \
  -H "INTERNAL-TOKEN: default_token"
```

```json
{"movements":[
  {"movement_key":"a891172f-...","created_at":"2026-10-08T22:42:10-03:00","direction":"DEBIT","movement_type":"PRINCIPAL","description":"Pix para Ana Souza","amount_cents":-50000,"balance_after_cents":150000,"transaction_key":"837bf409-...","counterparty_name":"Ana Souza"},
  {"movement_key":"5284dfe5-...","created_at":"2026-10-08T22:42:10-03:00","direction":"CREDIT","movement_type":"PRINCIPAL","description":"TED recebida de Carlos Lima","amount_cents":200000,"balance_after_cents":200000,"transaction_key":"397cac6f-...","counterparty_name":"Carlos Lima"}
],"next_cursor":null}
```

Quando há tarifa, ela aparece numa linha própria (`"movement_type": "FEE"`, "Tarifa de Pix"),
logo acima do valor. Para a próxima página, mande `?after=<next_cursor>`.

---

## 5. Todas as rotas

| Método e rota | O que faz |
|---|---|
| `GET /` | diz qual serviço é este (aberta) |
| `GET /health_check` | diz se a API está de pé (aberta, `204`) |
| `POST /clients` | cadastra PF ou PJ |
| `GET /clients/{client_key}` | consulta o cliente (CPF sai mascarado) |
| `POST /clients/{client_key}/accounts` | abre a conta (uma por cliente) |
| `GET /accounts/{account_key}` | consulta a conta e o saldo |
| `PATCH /accounts/{account_key}` | bloqueia, reativa ou encerra, com motivo (encerrar só com saldo zero) |
| `POST /accounts/{account_key}/transactions` | envia Pix (`pix_key`) ou TED (banco, agência, conta e dígito) |
| `POST /webhook/central_bank/teds` | TED recebida de outro banco |
| `POST /webhook/central_bank/pix` | Pix recebido de outro banco (pela chave: CPF, CNPJ ou e-mail) |
| `GET /accounts/{account_key}/statement` | extrato paginado (`limit` de 1 a 100, padrão 50; `after`) |

Os status de cada rota (`400`, `404`, `409`, `422`, `503`) e o que torna cada uma idempotente
estão na tabela de rotas do [RFC](rfc.md).

---

## 6. Os erros

Todo erro responde no mesmo formato, com um código próprio, e nunca com stack trace:

```json
{"title":"Insufficient balance","description":"The account balance does not cover the amount plus the fee.","translation":"O saldo da conta não cobre o valor mais a tarifa.","code":"QIT004006"}
```

| Faixa | De quem é | Onde |
|---|---|---|
| `QIT000…` | erros gerais: corpo inválido (`001`), sem `INTERNAL-TOKEN` (`002`, status `403`), rota inexistente (`404`), método não aceito (`405`), erro inesperado (`500`) | `src/errors/base_error.py` |
| `QIT002…` | cliente | `src/errors/custom_errors.py` |
| `QIT003…` | conta | idem |
| `QIT004…` | transação | idem |
| `QIT005…` | tarifa | idem |
| `QIT006…` | extrato | idem |

Um código nunca se repete: se repetir, a API não sobe (checagem `error_verification`, em
`src/errors/base_error.py`).

---

## 7. Configuração

Toda configuração vem de variável de ambiente, com valor padrão no `docker-compose.yml`. Para
trocar algo, copie o exemplo e edite (o `.env` nunca vai para o Git):

```bash
cp .env.example .env
```

| Variável | Padrão | Para quê |
|---|---|---|
| `API_PORT` | `3000` | porta da API na sua máquina |
| `DB_PORT` | `5432` | porta do banco na sua máquina (mude também a porta da `DATABASE_URL`) |
| `MOCKSERVER_PORT` | `1080` | porta do Banco Central fake na sua máquina |
| `INTERNAL_TOKEN` | `default_token` | valor exigido no cabeçalho `INTERNAL-TOKEN` |
| `CENTRAL_BANK_API_TIMEOUT` | `5` | quantos segundos o envio para outro banco espera pelo Banco Central |

---

## 8. Quando dá errado

**`port is already allocated`.** Outro programa usa a porta (é comum um Postgres local na
5432). Ponha outras portas no `.env` (seção 7) e suba de novo. Se mudar o `DB_PORT`, mude
também a porta da `DATABASE_URL`, no mesmo arquivo.

**`failed to connect to the docker API`.** O Docker não está ligado. Abra o Docker Desktop
(Mac/Windows) ou rode `sudo systemctl start docker` (Linux).

**`Não consegui falar com a API`** ao rodar o `pytest`. O projeto não está de pé, ou a porta do
`.env` não é a que ele está usando. Suba com `docker compose up -d --wait`.

**Mudou o `database/database.sql` e nada aconteceu.** Ele só roda quando o banco nasce.
Recomece do zero: `docker compose down -v && docker compose up -d --wait` (apaga os dados).

**Para ver o que a API está dizendo:** `docker compose logs -f api`. Toda resposta traz um
cabeçalho `x-request-id`, que aparece nas linhas do log daquela requisição.

---

## 9. As pastas

```
src/
  app.py          ← liga tudo: rotas, middlewares e tratamento de erro
  constants.py    ← configurações, lidas do ambiente
  resources/      ← recebe a requisição HTTP e devolve a resposta
  schemas/        ← o formato do que entra (JSON Schema)
  controllers/    ← as regras de negócio: o que pode e o que não pode
  repositories/   ← as conversas com o banco
  models/         ← as tabelas, descritas em Python
  dtos/           ← traduz o objeto do banco no JSON que sai
  errors/         ← os erros da API, cada um com seu código
  middlewares/    ← o que acontece com toda requisição (token, sessão, log)
  connectors/     ← as conversas com outros serviços (Banco Central fake)
  utils/          ← cálculos sem camada: documento, dígito, tarifa, chave Pix
database/
  database.sql    ← as tabelas, as restrições e os dados iniciais (tarifas)
tests/
  integration/    ← testes black box, por assunto
  unit/           ← cálculos isolados
```

O caminho de uma requisição é sempre o mesmo, e cada camada só conversa com a vizinha:

```
requisição → middlewares → schema → resource → controller → repository → banco
```

As proteções do dinheiro também estão no próprio banco de dados: saldo nunca negativo,
transações e lançamentos que nunca são editados nem apagados, tarifa só em envio de PJ e
e-mail único entre clientes e representantes. Se o código tiver um bug, o banco não deixa o
bug virar dado errado.

---

## 10. A licença

**MIT** — veja o arquivo `LICENSE`.

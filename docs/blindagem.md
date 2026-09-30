# Blindagem por camadas — conta PJ, autenticação e transações

Documento de apoio à [RFC da conta transacional](../rfc.md). Ele descreve os controles de segurança propostos; não substitui análise jurídica, regulatória, testes de segurança ou uma plataforma completa de PLD/FT.

## 1. O que cada validação realmente prova

| Verificação | O que prova | O que não prova |
|---|---|---|
| Dígitos verificadores de CPF/CNPJ | O número tem estrutura matematicamente válida | Que existe, está regular ou pertence ao solicitante |
| Consulta oficial de CPF/CNPJ | O cadastro existe, sua situação e os dados oficiais consultáveis | Que quem preencheu o formulário controla a identidade |
| QSA/representação | A pessoa consta como sócia/administradora, ou apresentou procuração válida | Que é a pessoa física presente na sessão |
| E-mail e telefone confirmados | A pessoa controla aqueles canais naquele momento | Identidade civil ou vínculo empresarial; SMS também sofre troca de SIM |
| Documento + biometria com prova de vida | A pessoa presente se parece com o titular do documento/base consultada | Sozinha, autorização para representar a empresa |
| e-CNPJ/certificado ICP-Brasil | Posse de credencial vinculada à pessoa jurídica e responsável identificado | Que toda transação futura é legítima |
| Senha/MFA | Controle dos autenticadores cadastrados | Titularidade inicial, se o cadastro já nasceu fraudulento |

Nenhuma verificação isolada confirma “o CNPJ é meu”. A confiança vem da combinação das evidências e da preservação de seus resultados para auditoria.

**Score de crédito não comprova identidade.** Ele estima risco de inadimplência e seria relevante para crédito, cheque especial ou limite financiado. Como o MVP oferece apenas saldo próprio, não deve aprovar ou recusar titularidade pelo score de crédito. A blindagem usa uma decisão de risco antifraude, baseada em consistência cadastral, dispositivo, velocidade, destinatário, valor e comportamento; eventual bureau é apenas um sinal adicional, com finalidade e justificativa.

## 2. Onboarding blindado de empresa e representante

### 2.1 Fluxo proposto

1. Receber CNPJ, dados da empresa, representante, contatos e aceite dos termos. Normalizar CPF/CNPJ sem pontuação, e-mail em formato canônico e telefone em E.164.
2. Validar schema, tamanho e dígitos verificadores localmente. Esta etapa é barata e elimina erros; não aprova o cadastro. Desde julho de 2026, novas inscrições podem usar CNPJ alfanumérico: os 12 primeiros caracteres aceitam letras e números e os dois últimos continuam sendo dígitos verificadores calculados por módulo 11. CNPJs numéricos antigos continuam válidos; portanto, armazenar como `CHAR(14)`/texto em maiúsculas e nunca converter para inteiro ou aceitar somente `[0-9]`.
3. Consultar uma fonte oficial/autorizada para situação cadastral, razão social, natureza jurídica, endereço, atividade e QSA. Não confiar nesses campos enviados pelo navegador.
4. Comparar os dados informados com os oficiais e exigir CNPJ em situação aceita pela política. Divergências relevantes enviam o caso para revisão; não devem ser corrigidas silenciosamente.
5. Confirmar que o CPF pertence ao representante informado e que ele consta no QSA. Quando não constar, exigir procuração/documento de representação e revisão manual ou validação especializada.
6. Validar a identidade da pessoa física com documento e prova de vida/biometria por provedor autorizado. Uma alternativa de alta confiança para a empresa é desafio assinado com certificado ICP-Brasil/e-CNPJ.
7. Confirmar separadamente e-mail e telefone com códigos únicos, aleatórios, de uso único, curta validade, limite de tentativas e armazenamento apenas do hash do código.
8. Calcular o risco do onboarding: CNPJ recém-aberto, representante divergente, muitas tentativas, mesmo dispositivo em várias empresas, proxy suspeito ou contatos reutilizados elevam risco. O resultado é `APPROVED`, `REVIEW` ou `BLOCKED`, com motivos.
9. Criar cliente e representante como `PENDING`. Somente após todas as etapas obrigatórias, promover para `ACTIVE` e permitir a abertura da conta.
10. Registrar quais fontes foram verificadas, resultado, versão da regra e horário. Evitar persistir imagem biométrica ou documento bruto quando basta guardar referência e resultado do provedor.

### 2.2 MVP e evolução

**MVP do bootcamp:** algoritmo de CPF/CNPJ, consulta externa simulada por connector, confirmação de e-mail/telefone simulada, cruzamento de representante, estados `PENDING/ACTIVE/BLOCKED`, limite de tentativas e trilha de auditoria.

**Produção:** contrato com fonte oficial/autorizada, biometria com prova de vida, análise de procuração, e-CNPJ quando aplicável, política PLD/FT, privacidade/LGPD, revisão manual e monitoramento contínuo. A API pública do Conecta Gov tem público e condições de acesso específicos; não se deve presumir que qualquer empresa possa consumi-la diretamente.

### 2.3 Controles de contato

- Verificar e-mail e telefone no onboarding não significa usar ambos como fatores fortes em toda transação.
- Para login e transações sensíveis, preferir passkey/WebAuthn ou TOTP. SMS pode existir como alternativa, com verificação de troca de SIM/portabilidade quando disponível, mas não deve ser a única proteção para alto risco.
- Mudança de e-mail, telefone, senha ou autenticador exige sessão recente, segundo fator já cadastrado, notificação no canal antigo e período de segurança antes de elevar limites.
- Recuperação de conta deve ser tão forte quanto o cadastro; atendimento não pode remover MFA só com informações fáceis de descobrir.

## 3. Senhas, sessões e segredos

Senha não deve ser criptografada de modo reversível. Deve ser derivada por função lenta e resistente a ataques offline:

1. Usar Argon2id por biblioteca madura; os parâmetros devem ser calibrados e versionados para o ambiente.
2. Gerar salt aleatório e único para cada senha. Bibliotecas corretas incluem salt e parâmetros no próprio hash.
3. Opcionalmente usar pepper separado do banco, em secret manager; nunca no código ou `.env` versionado.
4. Aceitar frases longas, bloquear senhas comuns/vazadas, não criar perguntas secretas e não exigir troca periódica sem indício de comprometimento.
5. Comparar hashes em tempo constante e reprocessar o hash no próximo login quando os parâmetros envelhecerem.
6. Nunca registrar senha, OTP, token completo, chave PIX sensível ou payload biométrico em logs.

Sessões devem ter access token curto, refresh token rotativo e revogável, `representative_id`, `client_id`, escopos, emissão e expiração. O refresh token persistido deve ser hasheado. Logout, troca de senha, bloqueio do representante ou suspeita de roubo revogam sessões ativas.

## 4. Autorização: impedir acesso pela troca do ID

UUID reduz enumeração, mas não é controle de acesso. Toda rota de conta executa autorização em nível de objeto:

```text
representante autenticado
        ↓
representante está ACTIVE?
        ↓
representante.client_id == account.client_id?
        ↓
papel permite a operação?
        ↓
conta está ACTIVE?
```

Regras obrigatórias:

- O servidor obtém `representative_id` e `client_id` da sessão validada, nunca do corpo da requisição.
- O repository busca a conta já restringindo titularidade: `account_key = :key AND client_id = :session_client_id`.
- Não existe rota para alterar `balance_cents`, `client_id`, movimentos ou titularidade diretamente.
- DTOs nunca devolvem `id` interno, `password_hash`, token, CPF completo ou dados de outro cliente.
- Um representante pode ter papéis, como `ADMIN`, `OPERATOR` e `VIEWER`; transferir exige permissão própria e pode exigir dupla aprovação acima de um limite.
- A mesma regra vale para leitura de conta, extrato e comprovante. Não basta proteger apenas o `POST`.

Responder `404` para objeto inexistente ou alheio evita confirmar que a conta de outra empresa existe. Todas as negativas relevantes entram no log de auditoria.

## 5. Transação segura, sem saldo negativo ou duplicidade

### 5.1 O cliente nunca controla o saldo

O navegador envia somente intenção: tipo, valor, destino e `Idempotency-Key`. O servidor:

- interpreta valor como inteiro positivo em centavos;
- calcula tarifa e total no backend;
- carrega saldo diretamente do banco;
- valida limites e risco;
- ignora qualquer `balance`, `fee`, `client_id`, `status` ou `account_id` enviado pelo cliente;
- usa queries parametrizadas/ORM, nunca concatenação de SQL.

Alterar JavaScript, JSON ou botão no navegador não muda essas regras.

### 5.2 Saída PIX/TED, passo a passo

1. Middleware autentica sessão, aplica limite de requisições e cria `request_id`.
2. Schema valida tipos, centavos positivos, modalidade e campos obrigatórios do destino.
3. Controller autoriza o representante naquela conta e verifica permissões e estado.
4. Repository procura `(account_id, idempotency_key)`. Mesma chave e mesmo fingerprint devolvem a resposta anterior; mesma chave com outro corpo recebe `409`.
5. Antifraude avalia valor, velocidade, horário, dispositivo, destinatário novo, alterações cadastrais recentes e tentativas recusadas. Alto risco exige autenticação adicional, revisão ou bloqueio.
6. Inicia uma transação no PostgreSQL e trava a conta com `SELECT ... FOR UPDATE`.
7. Relê saldo e tarifa após obter a trava. Exige `balance_cents >= amount_cents + fee_cents` e conta `ACTIVE`.
8. Cria `financial_transaction`, movimentos imutáveis `PRINCIPAL` e `FEE`, e atualiza `account.balance_cents`. Um único `COMMIT` torna tudo visível; qualquer erro causa `ROLLBACK`.
9. Responde com `transaction_key` e estado. Nunca usa `GET` para debitar e nunca repete automaticamente um `POST` sem a mesma chave de idempotência.

A restrição `CHECK (balance_cents >= 0)` é a última barreira, não a única. Uma restrição única em `(origin_account_id, idempotency_key)` impede duplicação mesmo se dois processos passarem pela primeira consulta ao mesmo tempo.

### 5.3 Transferência entre duas contas internas

1. Autorizar somente a conta de origem; o recebedor não precisa autorizar o crédito.
2. Travar origem e destino sempre na ordem crescente de `account.id`, reduzindo deadlocks.
3. Validar saldo da origem.
4. Criar, no mesmo commit, débito da origem, crédito do destino, tarifa, novos saldos e uma única transação financeira.
5. Depois do commit, publicar a notificação. A notificação não confirma o dinheiro; o commit e o extrato são a fonte de verdade.

Assim não existe estado em que a origem perdeu o valor e o destino interno não recebeu.

### 5.4 PIX/TED externo

Não existe uma transação ACID única entre nosso PostgreSQL e outro banco. O fluxo precisa de estados:

1. Reservar/debitar localmente e gravar `PROCESSING` com referência única.
2. Enviar ao provedor com identificador idempotente, TLS, timeout e autenticação do parceiro.
3. Confirmação válida muda para `COMPLETED`; rejeição definitiva cria movimentos inversos de `REVERSAL`.
4. Timeout permanece inconclusivo; não reenviar cegamente. Consultar o provedor ou reconciliar pela referência.
5. Webhook de entrada exige assinatura/autenticação, validação de timestamp e proteção contra replay. A referência externa tem restrição `UNIQUE`.
6. Processar webhook e crédito em uma transação local. Repetição do mesmo evento devolve sucesso sem creditar novamente.

Para não perder notificações após o commit, uma evolução de produção usa outbox: o evento é salvo na mesma transação do dinheiro e um worker o publica com retentativa. O consumidor também usa inbox/referência única.

## 6. `account_movement` e extrato invioláveis

- Movimento financeiro confirmado não sofre `UPDATE` nem `DELETE` pela aplicação.
- Correção acontece por novo movimento `REVERSAL`, ligado à transação original.
- `balance_after_cents` facilita auditoria, mas o sistema também reconcilia periodicamente `account.balance_cents` com a soma dos movimentos.
- Apenas o serviço financeiro recebe permissão de inserir movimentos e atualizar saldo; usuário da API e conectores não acessam o banco diretamente.
- Índices e constraints: `(account_id, created_at, id)` para extrato; pares únicos para movimento/tipo quando necessário; FKs obrigatórias; valores positivos.
- Um job de conciliação sinaliza qualquer divergência e bloqueia movimentação até investigação; não “conserta” saldo silenciosamente.

## 7. Bots, abuso e alteração maliciosa

| Ameaça | Controles principais |
|---|---|
| Tentativa massiva de senha/OTP | rate limit por conta, IP e dispositivo; atraso progressivo; bloqueio temporário; alerta |
| Cadastro automatizado | limites, CAPTCHA como sinal auxiliar, reputação de IP/dispositivo, unicidade e revisão por risco |
| Roubo de sessão | TLS, cookie `HttpOnly/Secure/SameSite` quando aplicável, tokens curtos, rotação e revogação |
| Troca do `account_key` | autorização por titularidade em toda busca; UUID é apenas identificador público |
| Alteração de valor no navegador | valor, tarifa, saldo e permissões recalculados no servidor |
| Repetição/reentrância | idempotência única, fingerprint, trava de linha e commit atômico |
| Bot esvaziando a conta | limite por janela, limite diário, destinatário novo, step-up MFA, velocidade e bloqueio de risco |
| SQL injection | schemas estritos e queries parametrizadas/ORM |
| Webhook falso ou repetido | autenticação/assinatura, timestamp, proteção contra replay e referência única |
| Funcionário/serviço alterando saldo | menor privilégio no banco, movimentos imutáveis, auditoria e conciliação |

Limites devem existir por representante, conta e modalidade: quantidade por minuto, valor por transação e total diário. Mudança de senha, MFA, telefone ou representante pode reduzir temporariamente limites e bloquear novos destinatários.

## 8. Responsabilidade de cada camada

| Camada | Controles |
|---|---|
| `middlewares/` | autenticação, `request_id`, rate limit, tamanho do corpo, headers seguros, contexto da sessão |
| `schemas/` | formato, campos permitidos, limites de tamanho, enums, centavos positivos; rejeitar campos desconhecidos |
| `resources/` | contrato HTTP correto e DTO de saída; não decide segurança financeira |
| `controllers/` | autorização por titularidade/papel, estados, limites, risco, ordem do fluxo e commit |
| `repositories/` | consultas sempre escopadas ao cliente, locks, idempotência e persistência; não decide regra |
| `models/database` | PK/FK/UNIQUE/CHECK, saldo não negativo, integridade e privilégios mínimos |
| `connectors/` | TLS, credenciais do parceiro, timeout, validação da resposta e correlação; não aprova cliente ou transação |
| `dtos/` | mascaramento e lista explícita de campos; nunca expõe segredo ou ID interno |
| `logs/audit` | quem, o quê, quando, resultado e `request_id`, sem senha, OTP, token ou biometria |

## 9. Ordem recomendada de implementação e testes

### MVP obrigatório

1. Constraints do banco, centavos inteiros e uma conta por cliente.
2. Hash de senha com Argon2id e sessões ligadas ao representante.
3. Autorização de objeto em conta, extrato e transação.
4. Validação de CPF/CNPJ e connector oficial simulado.
5. Estados de onboarding e confirmação simulada de e-mail/telefone.
6. Idempotência, `SELECT FOR UPDATE`, saldo + movimentos no mesmo commit.
7. Regras antifraude explicáveis: valor, velocidade, destinatário novo e mudanças recentes.
8. Auditoria, rate limit e testes de segurança/concorrência.

### Testes que provam a blindagem

- representante A tenta consultar ou debitar conta de B: `404`, nenhuma alteração;
- troca de `account_key`, `client_id`, tarifa, saldo ou status no JSON: rejeitado/ignorado conforme contrato;
- duas saídas simultâneas que juntas excedem o saldo: apenas uma confirma;
- mesma `Idempotency-Key` enviada 100 vezes: um único débito;
- mesma chave com outro valor/destino: `409`;
- falha entre débito, tarifa e crédito interno: rollback integral;
- webhook repetido: um único crédito;
- webhook sem autenticação ou fora da janela: recusado;
- conta/representante bloqueado: nenhuma movimentação;
- movimento original permanece após estorno; surge movimento inverso;
- saldo da conta fecha com os movimentos após cada cenário;
- senha, OTP, token e CPF completo não aparecem em logs ou DTOs.

## 10. Invariantes contra adulteração

“Campo escondido na interface” não é segurança. A API presume que o usuário controla completamente navegador, aplicativo, JSON, headers e ordem das chamadas. A proteção nasce de três classificações.

### 10.1 Quem pode definir cada campo

| Classe | Exemplos | Regra |
|---|---|---|
| Intenção informada pelo cliente | modalidade, valor pretendido, chave PIX ou dados TED, descrição opcional | Aceita somente no endpoint de criação, por allowlist e schema estrito; ainda não é verdade financeira |
| Dado resolvido pelo servidor | conta de origem, titularidade, nome/documento do favorecido, instituição, tarifa, limites, risco | Nunca aceito do payload; calculado ou consultado no backend |
| Dado exclusivamente sistêmico | IDs, UUIDs, saldo, status, timestamps, `client_id`, referências, fingerprint, `balance_after_cents` | Não aparece em schema de escrita e não é atribuído por cópia genérica do payload |
| Snapshot financeiro imutável | origem, destino resolvido, tipo, valor, tarifa e solicitante após confirmação | Não recebe `UPDATE`; qualquer mudança cria nova intenção e nova autorização |
| Transição controlada | `PENDING → AWAITING_AUTHORIZATION → PROCESSING → COMPLETED/FAILED/REVERSED` | Somente métodos internos específicos mudam estado; nunca um `PATCH status` genérico |

Implementação obrigatória:

- usar DTO/schema de entrada separado do model de banco e `additionalProperties: false`;
- montar objetos campo a campo por allowlist; nunca `Model(**payload)`, `setattr` em laço ou merge de JSON no model;
- rejeitar campos sistêmicos, em vez de apenas ignorá-los silenciosamente;
- usar comandos distintos, como `CreateTransactionInput` e `AuthorizeTransactionInput`; nenhum deles contém saldo, tarifa, status, origem ou nome do favorecido;
- não oferecer `PUT/PATCH/DELETE` para `financial_transaction` ou `account_movement`;
- calcular IDs, chaves, timestamps, tarifa, titularidade, status e saldos exclusivamente no servidor.

Isso previne mass assignment: o ataque em que alguém acrescenta `balance_cents`, `status`, `client_id`, `fee_cents` ou `is_admin` a um JSON esperando que o framework copie tudo.

### 10.2 Destino e valor vinculados à autorização

O usuário necessariamente escolhe para onde deseja transferir, mas só na criação da intenção. Depois da resolução e da confirmação, o destino não pode mudar:

1. `POST /accounts/{account_key}/transactions` recebe modalidade, valor e identificador do destino.
2. O servidor autoriza a conta de origem, resolve o favorecido via DICT/provedor ou valida os dados TED e ignora nome/documento enviados como “verdade”.
3. O servidor calcula tarifa, cria `transaction_key` e grava snapshot de origem, destino resolvido, valor, tarifa, solicitante e expiração no estado `AWAITING_AUTHORIZATION`.
4. O servidor produz um `authorization_fingerprint` sobre representação canônica de `transaction_key + origin + destination + amount + fee + type + expires_at`. O fingerprint é calculado pelo servidor; um desafio enviado ao cliente é assinado/HMAC e tem uso único.
5. A tela segura mostra favorecido, instituição, documento mascarado, valor e tarifa. A autenticação adicional confirma exatamente esses dados — princípio “What You See Is What You Sign”.
6. `POST /transactions/{transaction_key}/authorizations` recebe somente a prova de autenticação. Não recebe novo destino, valor, tarifa ou origem.
7. O servidor relê o snapshot, confere fingerprint, expiração, uso único, sessão, dispositivo/política e estado. Qualquer diferença invalida o desafio e gera alerta.
8. A execução usa somente o snapshot do banco. Se o usuário quiser mudar um centavo ou o destino, cancela a intenção e cria outra, com nova autorização.

Também ficam gravados `requested_by_representative_id`, `authorized_by_representative_id`, `authorized_at` e o método de autorização. Para empresas, valores elevados podem exigir duas pessoas diferentes: uma solicita e outra aprova.

### 10.3 Barreiras no banco, mesmo se o controller errar

- `account_movement`: conceder ao papel da aplicação `INSERT` e `SELECT`, revogando `UPDATE` e `DELETE`.
- `financial_transaction`: origem, destino, tipo, valor, tarifa, solicitante, idempotência e fingerprints ficam imutáveis desde o `INSERT`. Trigger permite mudar somente status e timestamps previstos pela máquina de estados. Alteração financeira exige cancelar e criar outra transação.
- `account`: o papel comum não altera `balance_cents` por operação genérica. A escrita financeira fica concentrada em repository/função transacional com privilégio mínimo.
- `CHECK`: valores positivos, saldo não negativo, origem diferente do destino quando aplicável e campos coerentes com PIX/TED.
- `UNIQUE`: `(origin_account_id, idempotency_key)`, `external_reference` e combinações que impeçam movimento principal/tarifa duplicados.
- FKs obrigatórias e `NOT NULL` impedem movimentos órfãos.
- Opcional em produção: Row-Level Security como segunda barreira, configurando o cliente da sessão por transação. RLS complementa, não substitui autorização na aplicação.
- Auditoria de alto valor deve sair para armazenamento append-only separado. Administrador do banco não pode ser considerado incapaz de adulterar o mesmo banco que administra.

## 11. Mapa ampliado de ameaças

| Ameaça esquecida com frequência | Cenário | Blindagem |
|---|---|---|
| Mass assignment | atacante envia `status=COMPLETED`, `fee=0` ou `balance=...` | schemas separados, allowlist e campos sistêmicos ausentes da entrada |
| TOCTOU/substituição de favorecido | autoriza A, malware troca para B antes da execução | snapshot imutável e autorização vinculada ao fingerprint |
| BOLA/IDOR | troca `account_key` ou `transaction_key` na URL | busca escopada ao `client_id` e papel em toda rota |
| Função administrativa exposta | usuário comum chama bloqueio, estorno ou ajuste | autorização por função, rotas administrativas separadas e default deny |
| Replay | repete autorização, POST ou webhook | nonce/challenge de uso único, idempotência, timestamp e referência única |
| Confused deputy | serviço interno usa seu privilégio para conta errada | identidade por serviço e usuário, escopo, audience e autorização do objeto |
| Webhook forjado | envia “PIX recebido” diretamente | mTLS/assinatura, allowlist quando aplicável, timestamp, anti-replay e consulta/reconciliação |
| Resposta externa adulterada | parceiro comprometido devolve favorecido/status falso | TLS, schema de resposta, correlação, assinatura quando disponível e reconciliação |
| SSRF em connector | entrada do usuário vira URL interna | host/base URL fixo e allowlisted; usuário fornece identificador, nunca URL; redirects controlados |
| Exaustão de recurso | corpo enorme, paginação ou filtros caros | limite de corpo, paginação máxima, timeout, pool, rate limit e índices |
| Enumeration | varre UUIDs, e-mails, CNPJs e respostas diferentes | autorização, respostas uniformes, rate limit e monitoramento |
| PII em logs | CPF/e-mail/token aparece em URL ou exceção | redaction, proibir segredo/query sensível, acesso e retenção de logs |
| Token roubado | atacante usa sessão legítima | tokens curtos, rotação, revogação, binding/risco do dispositivo e step-up |
| SIM swap/recuperação fraca | troca telefone e esvazia conta | canal antigo, cooling-off, passkey/TOTP e limites reduzidos |
| Alteração cadastral seguida de saque | toma conta e muda contato/MFA | alertas, bloqueio temporário de novo favorecido e step-up |
| Insider/credencial de serviço | operador altera saldo ou apaga trilha | menor privilégio, dupla aprovação, trilha externa e conciliação |
| Dependência/imagem comprometida | pacote malicioso entra no build | versões fixas, hashes/lock, scanner, SBOM, imagem por digest e CI protegido |
| Backup adulterado ou indisponível | restauração perde movimentos | backup criptografado, imutável, teste de restore e conciliação |
| Clock/timezone inconsistente | expiração/replay e ordem do extrato falham | UTC, `TIMESTAMPTZ`, relógio sincronizado e ordenação com desempate por ID |
| Erro detalhado | stack trace revela SQL/segredo | handler uniforme, mensagem pública mínima e detalhe apenas em log sanitizado |
| Endpoint esquecido | versão antiga mantém controle fraco | inventário de rotas, versionamento, remoção explícita e testes por endpoint |

### Controles operacionais que o código sozinho não resolve

- TLS obrigatório até o proxy e entre serviços; mTLS ou identidade forte para chamadas internas sensíveis.
- Segredos em secret manager, rotação, versões e separação por ambiente; nunca defaults em produção.
- Banco sem porta pública, rede privada, criptografia de disco, backup e credencial exclusiva por serviço.
- Produção sem `--reload`, sem debug, sem documentação administrativa pública e com hosts/proxies confiáveis configurados.
- WAF/API gateway como camada auxiliar, não substituto de autorização.
- Alertas para picos de recusas, mudança de destino, muitas idempotency keys, divergência de saldo e alteração de MFA.
- Plano de resposta: bloquear conta/sessão, preservar evidência, reconciliar, comunicar e recuperar com dupla aprovação.
- Revisão de acesso de funcionários e serviços, segregação de funções e rotação de credenciais.
- Testes SAST, dependências, container, segredo, DAST e pentest antes de produção.

## 12. Resultado da varredura no projeto-base

O repositório atual é deliberadamente educacional e ainda não implementa as entidades financeiras. Os pontos abaixo são lacunas para o desenvolvimento, não evidência de exploração.

### Prioridade P0 — antes de movimentar dinheiro

1. **Autenticação compartilhada:** `src/middlewares/internal_token.py` aceita um único `INTERNAL-TOKEN`; não existe identidade de representante, sessão, MFA, papéis ou revogação. Um token vazado acessa todas as rotas.
2. **Sem autorização de objeto:** o repository busca apenas pela key. Na solução financeira, toda busca deve incluir o `client_id` da sessão e o papel do representante.
3. **Credenciais padrão e banco publicado:** `docker-compose.yml` usa `default_token`, usuário/senha `bootcamp`, publica PostgreSQL na máquina e inicia API com `--reload`. Isso é aceitável apenas localmente; produção deve falhar ao detectar default, usar secrets e rede privada.
4. **Webhook sem autenticidade ou replay protection:** a rota de exemplo usa apenas token compartilhado e incrementa estado a cada chamada. Webhook financeiro precisa assinatura/mTLS, timestamp, referência única e idempotência.
5. **Sem rate limit ou proteção de fluxo:** não há limites para login, OTP, cadastro, consulta ou transação. Isso permite brute force, enumeração, automação e exaustão.
6. **Banco sem barreira de imutabilidade financeira:** o schema de exemplo não tem privilégios separados, triggers ou tabelas append-only. Isso precisa nascer junto das tabelas financeiras.

### Prioridade P1 — antes de expor a API

1. **PII na query string e no log:** `request_logger.py` registra a query completa, enquanto a listagem aceita `email` e `document_number`. CPF/CNPJ/e-mail não devem ir à URL nem ao log; filtros sensíveis precisam redaction ou contrato diferente.
2. **Token estático comparado diretamente:** substituir o token global por autenticação por representante e identidade por serviço; chamadas internas não devem herdar poder total só por estarem “dentro”.
3. **Connector confia demais na resposta:** há timeout e o `requests` valida TLS por padrão, pontos positivos, mas faltam schema/tamanho de resposta, host allowlist, política de redirect, correlação, circuit breaker e tratamento seguro de erro.
4. **Sem limite global de corpo/conteúdo:** schemas limitam alguns campos, mas não há limite de bytes, tipos de conteúdo aceitos ou proteção para payload comprimido.
5. **Sem política explícita de headers/host/proxy:** definir TLS no edge, Trusted Host, CORS mínimo se houver navegador, security headers e configuração correta de proxy.
6. **Sem trilha de auditoria de segurança:** existe `request_id` e log de rota, mas não eventos estruturados de login, autorização, troca cadastral, decisão de risco, bloqueio e transição financeira.
7. **Privilégio amplo no banco:** a API usa a mesma credencial geral. Produção precisa de papéis/privilégios mínimos e acesso administrativo separado.

### Controles positivos já presentes

- JSON Schemas usam `additionalProperties: false`, uma boa base contra campos extras.
- SQLAlchemy constrói queries parametrizadas; não foi encontrada concatenação manual de SQL.
- O logger não grava corpo nem headers da requisição.
- Há `request_id`, timeout de connector, rollback/close de sessão e commits explícitos.
- A imagem executa com usuário não root.
- Dependências estão fixadas por versão e segredos locais são ignorados pelo Git.

Esses controles devem ser preservados, complementados e cobertos por testes. Versão fixa sem hash, scanner e processo de atualização ainda não fecha risco de cadeia de suprimentos.

### Testes adicionais de adulteração

- enviar todos os campos sistêmicos conhecidos em cada endpoint e exigir `400`;
- autorizar transação, alterar destino/valor no cliente e confirmar: desafio inválido, nenhum débito;
- reutilizar autorização em outra `transaction_key`: recusado;
- confirmar duas vezes em paralelo: uma execução financeira;
- solicitar com representante `VIEWER`: `403`, ainda que ele pertença à empresa;
- acessar rota administrativa com token de usuário/serviço errado: `403/404`;
- tentar atualizar/deletar movimento diretamente com o papel SQL da aplicação: permissão negada;
- tentar transição de status fora da máquina de estados: banco/controller recusam;
- enviar URL, redirect ou resposta gigante ao connector: recusado;
- pesquisar CPF/e-mail e verificar que log não contém o valor;
- restaurar backup de teste e reconciliar saldos, movimentos e referências;
- comprometer uma barreira em teste (por exemplo, retirar check do controller) e provar que constraint/trigger ainda impede corrupção.

## 13. Fontes de referência

- [Resolução CMN nº 4.753 — identificação, qualificação e autenticação de titulares e representantes](https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50847/Res_4753_v6_L.pdf)
- [Consulta CNPJ — dados oficiais, situação cadastral e QSA](https://www.gov.br/conecta/catalogo/apis/consulta-cnpj)
- [Receita Federal — CNPJ alfanumérico e cálculo dos dígitos verificadores](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cnpj-alfanumerico)
- [Datavalid — validação biográfica, documental, biométrica e prova de vida](https://www.gov.br/pt-br/servicos/obter-solucao-digital-para-validacao-de-identidade-datavalid)
- [ICP-Brasil — certificado de pessoa jurídica e responsável de uso](https://www.gov.br/iti/pt-br/acesso-a-informacao/perguntas-frequentes/certificacao-digital)
- [NIST SP 800-63B — autenticação, senhas, MFA e rate limiting](https://pages.nist.gov/800-63-4/sp800-63b.html)
- [OWASP Password Storage — Argon2id, salt e pepper](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP API Security Top 10 2023 — objetos, propriedades, consumo de recursos, SSRF e integrações](https://api-security.owasp.org/editions/2023/en/0x00-header/)
- [OWASP Transaction Authorization — vinculação de valor/destino à autorização](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
- [OWASP Mass Assignment — allowlist e DTOs separados](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [NIST SP 800-207 — zero trust e menor privilégio por requisição](https://csrc.nist.gov/pubs/sp/800/207/final)
- [PostgreSQL — Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL — constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

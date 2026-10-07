# DB_API_Ishikawa

Serviço dedicado de **persistência e validação de credenciais** do ecossistema Educampo Ishikawa. Expõe uma API REST interna (`/v1`) cujo contrato espelha 1:1 as interfaces `IProducerRepository`, `IConsultantRepository` e `IDiagnosticResultRepository` da `API_Ishikawa_Educampo`.

**Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · PostgreSQL 16 · bcrypt · uv

## Status

| Fase | Conteúdo | Estado |
|---|---|---|
| F1 | Skeleton, consultores, `POST /v1/auth/verify` | ✅ Implementada |
| F2 | Produtores, `producers_managed` derivado, auth de produtor | ✅ Implementada |
| F3 | Resultados de diagnóstico (`/v1/diagnostic-results`) | 🔄 Em planejamento |
| F4 | Seed idempotente, hardening, deploy no Supabase | ⏳ Pendente |

Especificação completa: [feature_spec_db_api_ishikawa.md](./feature_spec_db_api_ishikawa.md) · Épico: [epic_db_api_ishikawa_service.md](./epic_db_api_ishikawa_service.md) · Roadmap: [feature_roadmap_persistencia_incremental.md](./feature_roadmap_persistencia_incremental.md)

## Arquitetura

```mermaid
graph LR
    FE["Site"] --> API["API_Ishikawa_Educampo"]
    API -->|"REST + X-Service-Token"| DB["DB_API_Ishikawa"]
    DB --> PG[("PostgreSQL")]
    subgraph "Ambientes"
        L["Dev / CI: Docker (postgres:16-alpine)"]
        S["Staging / Prod: Supabase (Postgres gerenciado)"]
    end
    PG -.-> L
    PG -.-> S
```

| Componente | Responsabilidade |
|---|---|
| `API_Ishikawa_Educampo` | Regras de negócio e IA, sessão (JWT) e autorização de papéis |
| **`DB_API_Ishikawa`** | Persistência, integridade, **hash bcrypt e verificação de credenciais**, lock otimista |
| PostgreSQL | Armazenamento. Docker local em dev/CI; **Supabase apenas como Postgres gerenciado** em staging/prod (sem SDK, Auth, Storage ou Realtime) |

Trocar de provedor de banco = trocar `DATABASE_URL`.

### Credenciais e login

- Senhas são salvas apenas como hash bcrypt; `hashed_password` **nunca** aparece em respostas.
- Login: a API Ishikawa chama `POST /v1/auth/verify` com `{email, password, role}` e recebe `{id, role}` (200) ou 401 idêntico para e-mail inexistente e senha errada.
- Cadastro: `POST /v1/consultants` cria consultores; um consultor cadastra produtores via `POST /v1/producers` (valida `consultant_id`). A senha é imutável no `PUT /v1/producers/{id}`.

## Endpoints

Todas as rotas `/v1` exigem o header `X-Service-Token`. Erros seguem RFC 7807 (`application/problem+json`). Listagens aceitam `limit` (máx. 200) e `offset` e devolvem `X-Total-Count`. Atualizações usam `If-Match: <version>` (412 em conflito).

| Recurso | Rotas |
|---|---|
| Consultores | `POST/GET /v1/consultants`, `GET/PUT /v1/consultants/{id}` |
| Produtores | `POST/GET /v1/producers`, `GET/PUT/DELETE /v1/producers/{id}` (filtros `email`, `nome`) |
| Auth | `POST /v1/auth/verify` |
| Saúde | `GET /health/live`, `GET /health/ready` |

Em desenvolvimento a documentação interativa fica em `/docs`.

## Configuração

Copie `.env.example` para `.env`:

| Variável | Descrição |
|---|---|
| `ENVIRONMENT` | `development` / `production` (em produção `/docs` fica desabilitado) |
| `API_V1_STR` | Prefixo das rotas (padrão `/v1`) |
| `DATABASE_URL` | URL SQLAlchemy (`postgresql+psycopg://...`) |
| `SERVICE_TOKEN` | Segredo compartilhado com a API Ishikawa. **Troque em produção** |
| `PORT` | Porta do serviço (`8001`) |

## Executando localmente

Com Docker (Postgres + API; API em `http://localhost:8002`, Postgres em `localhost:5433`):

```bash
docker compose up --build
```

Sem Docker para a API (precisa de um Postgres acessível em `DATABASE_URL`):

```bash
uv sync
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

## Testes

Os testes de integração usam Postgres real via testcontainers (requer Docker em execução).

```bash
uv run pytest
```

## Deploy: Render + Supabase

1. No Supabase, copie a connection string do **pooler (Supavisor)** (o host direto é IPv6 e o Render não tem saída IPv6).
2. No Render, defina `DATABASE_URL=postgresql+psycopg://postgres.<ref>:<senha>@aws-0-<regiao>.pooler.supabase.com:6543/postgres?sslmode=require` e um `SERVICE_TOKEN` forte.
3. Rode as migrações pelo modo *session* do pooler (porta `5432`): `alembic upgrade head`.
4. Habilite **RLS sem policies** nas tabelas `consultants`, `producers` e `diagnostic_results`, para que a `anon key` não leia hashes.

> [!NOTE]
> Pendente na F4: configurar `prepare_threshold=None` (pooler em modo *transaction*) e o tamanho do pool via settings, e automatizar o RLS em migração. Veja a [spec §13](./feature_spec_db_api_ishikawa.md).
> Evite Postgres em container no Render: o disco é efêmero e um deploy/restart apaga os dados. O free tier do Supabase pausa após ~7 dias sem atividade.

## Estrutura

```text
app/
├── main.py          # FastAPI, handlers RFC 7807
├── core/            # config, security (bcrypt, X-Service-Token), errors
├── api/             # health.py e v1/ (auth, consultants, producers)
├── schemas/         # DTOs Pydantic
├── services/        # regras de negócio
└── db/              # models, session, repositories
alembic/             # migrações (001 consultores, 002 produtores)
tests/               # unit/ e integration/ (testcontainers)
```

# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato baseia-se no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.0.0] - 2026-10-08

### Lançamento Inicial (General Availability - v1.0.0)

Primeira versão de produção do microsserviço **DB_API_Ishikawa**, dedicado à persistência relacional, autoridade de credenciais (bcrypt), isolamento com Row Level Security (RLS) e persistência de diagnósticos agronômicos para o Ecossistema Educampo Ishikawa.

### Added (Novas Funcionalidades)
- `[feat(consultants)]`: Módulo de Consultores (F1) com operações CRUD completas, verificação de credenciais (`POST /v1/auth/verify`) e hash seguro via bcrypt.
- `[feat(producers)]`: Módulo de Produtores (F2) com relacionamento 1:N com Consultores, restrições citext de email case-insensitive e gestão de fazendas.
- `[feat(diagnostic-results)]`: Módulo de Resultados de Diagnóstico Agronômico (F3) com persistência de payload JSONB e controle de concorrência otimista via headers `If-Match` / `ETag`.
- `[feat(auth)]`: Endpoint dedicado `POST /v1/auth/password` para troca de senhas de produtores e consultores com validação estrita da senha atual.
- `[feat(seed-hardening)]`: Importador idempotente de dados iniciais a partir de `farms.json` com CLI dedicada e inicialização opcional via lifespan.
- `[feat(infra)]`: Suporte híbrido ao PostgreSQL 16 (Docker local e Supabase Cloud via Supavisor pooler na porta 6543 e Session Mode na 5432).
- `[feat(security)]`: Autenticação Machine-to-Machine (M2M) obrigatória via cabeçalho `X-Service-Token`.
- `[test(security)]`: Suíte de testes de resiliência e segurança contra injeção SQL (SQLi fuzzing), route tampering, anti-enumeração de credenciais e proteção RFC 7807 (Problem Details).

### Database Migrations (Alembic)
- `001_initial_consultants`: Criação da tabela `consultants` com extensão `citext`.
- `002_create_producers`: Criação da tabela `producers` com foreign key para `consultants`.
- `003_create_diagnostic_results`: Criação da tabela `diagnostic_results` com payload JSONB e controle de versão.
- `004_supabase_rls_hardening`: Ativação do Row Level Security (RLS) no catálogo PostgreSQL do Supabase.
- `005_move_citext_to_extensions`: Isolamento da extensão citext no schema `extensions`.
- `006_optimize_indexes_and_deny_rls`: Remoção de índices duplicados e criação de políticas explícitas de negação de acesso direto anônimo.

### Documentation & Architecture
- Diagramas de arquitetura C4 e UML com visualização ERD, API UML e diagramas de sequência.
- Documentação viva em docstrings com rastreabilidade ao Single Source of Truth no Obsidian Vault.

---
*Release consolidada via Antigravity Agentic Workflows.*

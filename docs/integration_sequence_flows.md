# Diagramas de Sequência e Fluxos de Integração Inter-serviços

> [!NOTE]
> **Visão de Fluxo M2M:**
> Este documento detalha a dinâmica temporal e a troca de mensagens entre a `API_Ishikawa_Educampo` e o microsserviço `DB_API_Ishikawa`. Ele abrange os cenários críticos de autenticação de credenciais, atualização segura de senhas, persistência sob concorrência otimista e verificação de prontidão (*healthcheck*).
>
> *Ref: [[sdd-db-api-ishikawa]], [[sdd-db-api-password-management]] e [[db-api-integration]].*

---

## 1. Visão Geral dos Fluxos Críticos

O diagrama abaixo apresenta visualmente os dois principais fluxos da arquitetura: validação de credenciais (sem exposição de hashes) e persistência com controle otimista de concorrência.

### 1.1 Diagrama Renderizado (Imagem PNG)

![Diagramas de Sequência: Autenticação e Lock Otimista](/docs/assets/integration_sequence_flows.png)

---

## 2. Fluxo 1: Autenticação de Usuário e Verificação de Credenciais

### 2.1 Diagrama Mermaid Interativo

```mermaid
sequenceDiagram
    autonumber
    actor User as "Produtor / Consultor"
    participant MainAPI as "API_Ishikawa_Educampo (Porta 8001)"
    participant DBAPI as "DB_API_Ishikawa (Porta 8002)"
    participant PG as "Supabase (PostgreSQL 16)"

    User->>MainAPI: 1. POST /api/auth/login {email, password}
    Note over MainAPI, DBAPI: Chamada Interna Protegida por Token M2M
    MainAPI->>DBAPI: 2. POST /v1/auth/verify {email, password}<br/>[Header: X-Service-Token]
    DBAPI->>PG: 3. SELECT id, nome, email, hashed_password FROM consultants/producers
    PG-->>DBAPI: 4. Retorna registro (ou vazio)
    
    Note over DBAPI: 5. bcrypt.checkpw(password, hashed_password)<br/>(Comparação em Tempo Constante)

    alt Credenciais Válidas
        DBAPI-->>MainAPI: 6a. HTTP 200 OK {id, role, nome, email}
        MainAPI->>MainAPI: Gera cookie de sessão JWT (session_token)
        MainAPI-->>User: HTTP 200 OK {message: "Login realizado"}
    else Senha Incorreta ou Usuário Inexistente
        DBAPI-->>MainAPI: 6b. HTTP 401 Unauthorized (RFC 7807 ProblemDetails)
        MainAPI-->>User: HTTP 401 Unauthorized {detail: "Credenciais inválidas"}
    end
```

### 2.2 Princípios de Segurança Aplicados
* **Ocultação Absoluta do Hash:** O campo `hashed_password` é recuperado pelo DB_API do banco e consumido unicamente em memória para o cálculo do `bcrypt`. Ele **nunca** é enviado de volta para a `API_Ishikawa_Educampo`.
* **Defesa contra Ataques de Temporização:** Caso o e-mail não seja encontrado no banco, o DB_API executa um cálculo de verificação contra um hash falso pré-computado, garantindo que o tempo de resposta seja indistinguível entre usuário inexistente e senha incorreta.

---

## 3. Fluxo 2: Persistência com Controle Otimista de Concorrência

### 3.1 Diagrama Mermaid Interativo

```mermaid
sequenceDiagram
    autonumber
    actor Consultor as "Consultor Técnico"
    participant MainAPI as "API_Ishikawa_Educampo"
    participant DBAPI as "DB_API_Ishikawa"
    participant PG as "Supabase (PostgreSQL 16)"

    Consultor->>MainAPI: 1. Salvar Diagnóstico Zootécnico (dados alterados)
    Note over MainAPI, DBAPI: Envio da Versão Atual via Cabeçalho If-Match
    MainAPI->>DBAPI: 2. PUT /v1/diagnostic-results/{id} {payload}<br/>[Headers: X-Service-Token, If-Match: 1]
    
    DBAPI->>PG: 3. UPDATE diagnostic_results<br/>SET ..., version = 2, updated_at = now()<br/>WHERE producer_id = :id AND version = 1;

    alt Versão Coincide (Rows Affected = 1)
        PG-->>DBAPI: 4a. 1 linha atualizada
        DBAPI-->>MainAPI: 5a. HTTP 200 OK {producer_id, version: 2, updated_at}
        MainAPI-->>Consultor: HTTP 200 OK (Diagnóstico salvo com sucesso)
    else Versão Divergente / Concorrência (Rows Affected = 0)
        PG-->>DBAPI: 4b. 0 linhas atualizadas (Versão no banco já é > 1)
        DBAPI-->>MainAPI: 5b. HTTP 412 Precondition Failed<br/>{type: "version-mismatch", status: 412}
        MainAPI-->>Consultor: HTTP 409/412 "Conflito: outro consultor atualizou este diagnóstico."
    end
```

---

## 4. Fluxo 3: Atualização Segura de Senha (`POST /v1/auth/password`)

```mermaid
sequenceDiagram
    autonumber
    actor User as "Produtor / Consultor"
    participant MainAPI as "API_Ishikawa_Educampo"
    participant DBAPI as "DB_API_Ishikawa"
    participant PG as "Supabase (PostgreSQL 16)"

    User->>MainAPI: 1. POST /api/auth/password {current_password, new_password}
    MainAPI->>DBAPI: 2. POST /v1/auth/password {user_id, role, current_password, new_password}<br/>[Header: X-Service-Token]
    DBAPI->>PG: 3. SELECT hashed_password WHERE id = :user_id
    DBAPI->>DBAPI: 4. bcrypt.checkpw(current_password, hashed_password)
    
    alt Senha Atual Válida
        DBAPI->>DBAPI: 5. Gera novo salt e hash: bcrypt.hashpw(new_password)
        DBAPI->>PG: 6. UPDATE ... SET hashed_password = :new_hash, version = version + 1
        DBAPI-->>MainAPI: 7a. HTTP 200 OK {message: "Senha atualizada com sucesso"}
        MainAPI-->>User: HTTP 200 OK
    else Senha Atual Incorreta
        DBAPI-->>MainAPI: 7b. HTTP 401 Unauthorized {code: "INVALID_CURRENT_PASSWORD"}
        MainAPI-->>User: HTTP 400/401 "Senha atual incorreta"
    end
```

---

## 5. Fluxo 4: Sonda de Prontidão e Startup (`GET /health/ready`)

```mermaid
sequenceDiagram
    autonumber
    participant Kube as "Docker / Render Health Probe"
    participant DBAPI as "DB_API_Ishikawa"
    participant PG as "Supabase (PostgreSQL 16)"

    Kube->>DBAPI: 1. GET /health/ready
    DBAPI->>PG: 2. SELECT 1 (Ping de conexão no pool)
    alt Banco Conectado e Respondendo
        PG-->>DBAPI: 3a. Conexão OK
        DBAPI-->>Kube: 4a. HTTP 200 OK {"status": "ready", "database": "healthy"}
    else Supabase Inacessível ou Timeout
        PG-->>DBAPI: 3b. Conexão Recusada / Timeout
        DBAPI-->>Kube: 4b. HTTP 503 Service Unavailable {"status": "unhealthy"}
    end
```

---

## 🔗 Documentos Relacionados
* [Arquitetura das Tabelas do Supabase](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/database_schema_architecture.md)
* [Arquitetura de Componentes da API](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/api_architecture_and_components.md)
* [Guia de Integração e Consumo do DB_API](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/client_integration_guide.md)

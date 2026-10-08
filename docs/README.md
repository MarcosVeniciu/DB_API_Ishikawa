# Directory Documentation: `docs`

## Overview
* **Purpose:** Centro de documentação técnica, modelagem relacional do banco de dados, guias de arquitetura e especificações de integração M2M para desenvolvedores do ecossistema Educampo Ishikawa (com foco principal na consumidora `API_Ishikawa_Educampo`).
* **Layer:** Documentation / Architecture / Integration Specs

---

## Mapa de Documentações Técnicas

| Documento | Descrição e Propósito | Diagramas Incluídos |
| :--- | :--- | :--- |
| [database_schema_architecture.md](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/database_schema_architecture.md) | **Especificação das Tabelas do Supabase:** Dicionário de dados de `consultants`, `producers`, `diagnostic_results`, índices, chaves estrangeiras, `citext` e RLS. | • ERD em PNG (`docs/assets/database_erd_diagram.png`)<br/>• Diagrama de Classes Mermaid |
| [api_architecture_and_components.md](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/api_architecture_and_components.md) | **Arquitetura de Camadas e Componentes da API:** Divisão em Clean Architecture (Routers, Services, Repositories, Engine), DTOs Pydantic v2 e segurança M2M. | • UML em PNG (`docs/assets/api_architecture_uml.png`)<br/>• Diagrama de Componentes Mermaid |
| [integration_sequence_flows.md](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/integration_sequence_flows.md) | **Diagramas de Sequência Inter-serviços:** Fluxo temporal de autenticação bcrypt anti-timing attacks, atualização de senhas, concorrência otimista (`If-Match`) e healthcheck. | • Sequência em PNG (`docs/assets/integration_sequence_flows.png`)<br/>• Diagramas de Sequência Mermaid |
| [client_integration_guide.md](file:///e:/Codigos/Educampo/DB_API_Ishikawa/docs/client_integration_guide.md) | **Manual de Handoff para a API Principal:** Guia prático para os desenvolvedores da `API_Ishikawa_Educampo` implementarem os adaptadores HTTP (`Http*Repository`). | • Diagramas de fluxo e exemplos de código HTTP |

---

## Diretório de Assets (`docs/assets/`)
Contém os diagramas de alta resolução gerados em formato `.png` (220 DPI) para garantir que qualquer desenvolvedor consiga visualizar a arquitetura mesmo sem ferramentas ou extensões que renderizem Mermaid:
* `database_erd_diagram.png`: Diagrama de Entidade-Relacionamento e Classes das Tabelas.
* `api_architecture_uml.png`: Diagrama de Componentes e Camadas da API.
* `integration_sequence_flows.png`: Diagramas de Sequência de Autenticação e Lock Otimista.

---

## Decisões Arquiteturais & Trade-offs
* **Diagramas Duplos (PNG + Mermaid):** Permite edição viva dos diagramas via texto no Markdown (Mermaid) ao mesmo tempo em que oferece renderização visual imediata garantida (PNG) em qualquer visualizador de arquivos.
* **Isolamento de Persistência:** A camada de dados relacional é 100% isolada, servindo exclusivamente como autoridade do PostgreSQL e das credenciais.

---

## Contexto e Rastreabilidade no Obsidian
* SSOT Obsidian: `[[sdd-db-api-ishikawa]]`, `[[db-api-integration]]`, `[[2026-10-07-supabase-managed-postgres-and-credential-ownership]]`, `[[integration-index]]`.

# Avaliador de MITs TOTVS

Ferramenta CLI para auditoria automatizada de qualidade de documentações de projetos TOTVS (MITs - Metodologia de Implantação TOTVS).

## Objetivo

Avaliar documentos MIT contra critérios rigorosos de qualidade e retornar:
- **Nota** (0-10)
- **Recomendações** de melhoria (se nota < 10)

## Status

🚧 Em desenvolvimento

## MITs Suportadas

| MIT | Nome | Status |
|-----|------|--------|
| MIT041 | Desenho da Solução / Blueprint | 🚧 Em desenvolvimento |
| MIT043 | Especificação Técnica | ⏳ Planejado |
| MIT037 | Roteiro de Treinamento | ⏳ Planejado |
| MIT045 | Roteiro de Testes | ⏳ Planejado |
| MIT065 | Termo de Encerramento | ⏳ Planejado |

## Estrutura

```
├── samples/              # Exemplos de MITs para calibração
│   └── boas/mit41/       # Colocar arquivos .docx aqui (gitignore)
├── src/avaliador/        # Código fonte
└── opencode.json         # Configuração MCP para OpenCode
```

## Requisitos

- Python 3.10+
- Docling
- DTA Proxy API Key (TOTVS)

## Instalação

```bash
# Clonar repositório
git clone https://github.com/AJoao-totvs/Avaliador_MIT.git
cd Avaliador_MIT

# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
copy .env.example .env
# Editar .env com sua DTA_PROXY_API_KEY
```

## Uso

```bash
# Avaliar uma MIT041
avaliador "caminho/para/documento.docx"

# Output JSON
avaliador "documento.docx" --json

# Sem análise de imagens (mais rápido)
avaliador "documento.docx" --no-vision

# Ignorar cache
avaliador "documento.docx" --no-cache
```

## Configuração

Copie `.env.example` para `.env` e configure:

```bash
DTA_PROXY_API_KEY=sua_api_key_aqui
```

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                      AVALIADOR CLI                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Docling   │  │  Evaluator  │  │    Cache    │         │
│  │  (ingestão) │──│  (LLM call) │──│  (hash-based)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                          │                                  │
│                          ▼                                  │
│                  ┌───────────────┐                          │
│                  │   DTA PROXY   │                          │
│                  │ gemini-2.5-pro│                          │
│                  └───────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Critérios de Avaliação (MIT041)

### Pilar 1: Completude Estrutural (30%)
- Metadados do projeto
- Histórico de versões
- Lista de participantes
- Descrição AS IS
- Cobertura de processos

### Pilar 2: Qualidade das Regras e Fluxos (40%)
- Descrição de processos
- Critérios de aceitação
- Tabela de GAPs
- Diagramas BPMN

### Pilar 3: Governança e Aceite (30%)
- Tabela de aceite
- Premissas e restrições
- Definição de escopo

## Licença

Uso interno TOTVS

# TwoAgentSandbox

TwoAgentSandbox is a Python command-line project for running multiple AI agents
inside hardened, disposable Docker containers on a shared Docker network.

The current default workload runs two agents:

- `sandbox_agent`: the entry agent. It creates an HTML document from MariaDB data
  and owns the final `index.html` artifact.
- `company_header_agent`: a supporting A2A agent. It exposes an HTTP endpoint,
  reads the `company_name` MCP resource, and returns updated HTML with a
  `<header>` element injected into the document.

Shared sidecars provide network and tool infrastructure:

- Squid proxy for controlled outbound network access.
- MCP server sidecar for declared tools and resources.
- HAProxy sidecar for MariaDB TCP access from the MCP sidecar to the host.
- Optional code execution, Jina Reader, and Ollama sidecars for other
  capabilities.

> [!WARNING]
> This is an experimental sandboxing and sidecar orchestration project. It is a
> learning and hardening exercise, not a finished security model.

## Default Workload

On each default run:

1. `docker_sandbox` reads `src/sandbox_agent/sandbox_run.toml`.
2. It resolves all declared agents, sidecars, network settings, ACLs, and image
   requirements into `resolved-sandbox-plan.json`.
3. It builds or reuses one Docker image per unique functional agent image
   requirement.
4. It creates a per-run internal Docker network with deterministic IPs.
5. It starts the shared Squid, HAProxy, and MCP sidecars.
6. It starts `company_header_agent` as a detached A2A HTTP server.
7. It runs `sandbox_agent` as the foreground entry agent.
8. `sandbox_agent` calls the MCP tool `get_active_items`.
9. The MCP sidecar connects to MariaDB through `haproxy-sidecar:3306`.
10. `sandbox_agent` prepares an HTML document and calls `company_header_agent`
    through A2A.
11. `company_header_agent` reads the MCP resource `company_name`, injects a
    `<header>` element, and returns the updated HTML.
12. `sandbox_agent` saves the returned HTML as
    `/sandbox-output/site/index.html` and writes `/sandbox-output/answer.txt`.
13. When the entry agent exits, the Docker network and containers are torn down.

The generated HTML should contain:

```html
<header>Example Australian Company</header>
```

## Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m sandbox_agent
```

The host-side command delegates to `docker_sandbox`. Inside the container, the
same module runs the actual `sandbox_agent` workload.

Run artifacts are written under:

```text
.docker_sandbox/runs/run-YYYY-mm-dd-HH-MM-SS/
```

## Run-Level Spec

The run is declared by `src/sandbox_agent/sandbox_run.toml`:

```toml
schema_version = 1

agents = [
  "sandbox_spec.toml",
  "../company_header_agent/sandbox_spec.toml",
]

[execution]
mode = "entry_agent"
entry_agent = "agent_1"
order = [
  "agent_1",
  "company_header_agent",
]

[network]
enabled = true
internal = true
subnet = "172.28.0.0/24"

[squid_proxy]
default_allowed_domains = []
default_allowed_ip_addresses = []

[haproxy]
backend_host = "host.docker.internal"
default_ports = []

[mcp_sidecar]
default_tools = []
default_resources = []
```

The run-level file owns shared network and appliance defaults. It also names all
agent spec files and defines the execution model.

### Execution Mode

The default uses:

```toml
[execution]
mode = "entry_agent"
entry_agent = "agent_1"
```

In this mode, non-entry agents are started first as long-running A2A HTTP
servers. The entry agent is then run as the foreground process. When the entry
agent exits, the whole run is considered complete.

Sequential multi-agent execution is also supported by the planner/runtime, but
the default project goal is the entry-agent A2A model.

## Agent Specs

Each agent declares its own container and application needs.

`src/sandbox_agent/sandbox_spec.toml` declares the entry agent:

```toml
schema_version = 1
agent_id = "agent_1"
module = "sandbox_agent"

container_capabilities = [
  "network",
]

application_capabilities = [
  "mcp_client",
  "openai_agents",
]

[haproxy]
ports = [
  3306,
]

[mcp_sidecar]
tools = [
  "get_html_element_name",
  "get_active_items",
]
resources = []
```

`src/company_header_agent/sandbox_spec.toml` declares the supporting A2A agent:

```toml
schema_version = 1
agent_id = "company_header_agent"
module = "company_header_agent"

container_capabilities = [
  "network",
]

application_capabilities = [
  "mcp_client",
  "openai_agents",
]

[mcp_sidecar]
tools = []
resources = [
  "company_name",
]
```

Unknown keys, unknown capability values, duplicate IDs, invalid ports, and
invalid execution orders fail closed during parsing/planning.

## Per-Agent Images

Each agent receives a Docker image based on functional requirements. Agents with
the same functional image inputs share an image. Agents with different
functional inputs receive different images.

The image hash includes:

- run-level network, Squid, HAProxy, and MCP defaults
- agent container capabilities
- agent application capabilities
- agent environment declarations
- agent Squid, HAProxy, MCP tool, and MCP resource declarations

The image hash excludes non-functional identity/runtime details:

- `agent_id`
- Python module name
- container name
- assigned IP address
- run ID
- execution order

The current default run produces distinct images because the two agents declare
different MCP exposure requirements.

## Shared Sidecars

### Squid

Squid runs as `egress-gateway` on the internal Docker network. Agent containers
that declare `network` receive:

```text
HTTP_PROXY=http://egress-gateway:3128
HTTPS_PROXY=http://egress-gateway:3128
```

The generated Squid config uses source-IP ACLs:

- run-level defaults apply to all planned agent IPs
- agent-level allowlists apply only to that agent's source IP

### HAProxy

HAProxy runs with alias `haproxy-sidecar`. It reaches the Windows host through
Docker's `bridge` network and joins the internal sandbox network for other
containers.

The default MariaDB path is:

```text
MCP sidecar -> haproxy-sidecar:3306 -> host.docker.internal:3306
```

The generated HAProxy config uses source-IP ACLs for default and agent-specific
ports. The MCP sidecar is also allowed to use declared HAProxy ports because the
MariaDB connection originates from MCP tools.

### MCP Sidecar

The MCP sidecar runs with alias `mcp-sidecar`. Agents with `mcp_client` receive:

```text
MCP_SIDECAR_URL=http://mcp-sidecar:8000/mcp
```

For now, a single MCP sidecar exposes the union of all run-level and agent-level
declared tools/resources.

Implemented MCP tools include:

- `get_html_element_name`
- `get_active_items`
- `microsoft_docs_search`
- `microsoft_docs_fetch`
- `microsoft_code_sample_search`
- `jina_read_url`
- `run_python_script`

Implemented MCP resources include:

- `answer_format`: `mcp-sidecar://instructions/answer-format.md`
- `company_name`: `mcp-sidecar://company/name.txt`

MCP tool/resource calls are audited in `mcp-sidecar-tool-calls.jsonl`.

## A2A Helper Agent

`company_header_agent` implements a small dependency-free subset of A2A using
Python's standard HTTP server.

It supports:

- `GET /health`
- `GET /.well-known/agent.json`
- `POST /a2a` with JSON-RPC method `message/send`

It does not implement the full A2A protocol surface such as streaming, task
polling, cancellation, push notifications, authentication, or full schema
validation.

The entry agent calls the helper through a function tool:

```text
sandbox_agent OpenAI agent
  -> add_company_header(html_document)
       -> GET /.well-known/agent.json
       -> POST /a2a message/send
       <- updated HTML
  -> save_html_document("index.html", updated_html)
```

## Runtime Environment

The default workload needs these host environment variables:

```text
OPENAI_API_KEY=<OpenAI API key>
SANDBOX_TESTER_MARIADB_CREDENTIALS=<username,password>
```

`SANDBOX_TESTER_MARIADB_CREDENTIALS` is passed only to the MCP sidecar when
HAProxy is enabled. It must use a comma-separated value:

```text
sandbox_tester,password_goes_here
```

When HAProxy is enabled, the MCP sidecar receives:

```text
MARIADB_HOST=haproxy-sidecar
MARIADB_PORT=3306
MARIADB_DATABASE=agent_allowed
SANDBOX_TESTER_MARIADB_CREDENTIALS=<from host environment>
```

Agent containers do not receive `MARIADB_HOST`, `MARIADB_PORT`,
`MARIADB_DATABASE`, or `SANDBOX_TESTER_MARIADB_CREDENTIALS`.

## Run Artifacts

A successful default run contains files similar to:

```text
.docker_sandbox/runs/run-YYYY-mm-dd-HH-MM-SS/
  Dockerfile
  config.json
  gateway-logs.json
  gateway-start-results.json
  haproxy.cfg
  haproxy-sidecar-logs.json
  landlock-policy.json
  mcp-sidecar-exposure.json
  mcp-sidecar-logs.json
  mcp-sidecar-tool-calls.jsonl
  resolved-profile.json
  resolved-sandbox-plan.json
  run-metadata.json
  sandbox-spec.json
  seccomp-profile.json
  squid.conf
  stdout.txt
  stderr.txt
  agents/
    agent_1/
      answer.txt
      stdout.txt
      stderr.txt
      run-metadata.json
      site/index.html
    company_header_agent/
      stdout.txt
      stderr.txt
      run-metadata.json
```

`resolved-sandbox-plan.json` is the best debugging artifact for image names,
container names, IP addresses, sidecar exposure, and generated ACL intent.

## Capabilities

Supported container/application capabilities include:

- `network`
- `mcp_client`
- `openai`
- `openai_agents`
- `anthropic_claude`
- `anthropic_python`
- `playwright_chromium`
- `shell_access`
- `code_execution`
- `jina_reader`
- `ollama`
- `crewai`
- `google_adk`
- `ibm_beeai`
- `langchain`
- `langgraph`
- `microsoft_agent`
- `otto_agent`

Provider-backed capabilities can add provider domains and host environment
variables. With the default GPT-backed workload, the agents use hosted OpenAI
models and therefore need `OPENAI_API_KEY`.

## Sandbox Probes

The copied SandboxTester probe suite can be run against the generated sandbox:

```powershell
.\.venv\Scripts\python.exe -m sandbox_agent --test-sandbox
```

To serialize probe evidence for troubleshooting:

```powershell
.\.venv\Scripts\python.exe -m sandbox_agent --test-sandbox --serialize-evidence
```

## Requirements

- Python 3.11.
- PowerShell on Windows.
- Docker Desktop with Linux containers enabled.
- MariaDB running on the host and reachable from Docker as
  `host.docker.internal:3306`.
- A database named `agent_allowed` with an `items` table compatible with the
  default `get_active_items` query.
- A MariaDB user whose credentials are available in
  `SANDBOX_TESTER_MARIADB_CREDENTIALS`.
- `OPENAI_API_KEY` for the default GPT-backed workload.
- Network access during image builds to download Python packages and Docker base
  images.

## Setup

Create the virtual environment and install development dependencies:

```powershell
.\scripts\setup-dev.ps1
```

## Development Checks

Run formatting, linting, type checking, and tests:

```powershell
.\scripts\check.ps1
```

This runs:

- `ruff format .`
- `ruff check .`
- `pyright`
- `pytest`

## Architecture

The project has six main packages:

- `sandbox_agent`: the entry workload. It owns the OpenAI Agents SDK prompt,
  MCP calls, A2A client function tool, and final artifact saving.
- `company_header_agent`: the supporting OpenAI Agents SDK workload and small
  A2A HTTP server.
- `mcp_sidecar`: the MCP server container workload. It owns local MCP resources,
  local MCP tools, MariaDB access, Microsoft Learn proxy tools, Jina Reader
  client logic, code-execution client logic, and audit logging.
- `code_sidecar`: the optional no-network code-execution sidecar.
- `docker_sandbox`: the host/container harness. It owns TOML parsing, planning,
  per-agent image creation, Docker networking, sidecar startup, A2A helper
  startup, entry-agent execution, artifacts, and teardown.
- `sandbox_tester`: the copied probe suite used by `--test-sandbox`.

The default Docker topology is:

```text
Docker host
  docker_sandbox host runner
    |
    +-- Docker bridge network
    |     |
    |     +-- haproxy-sidecar-* container
    |           backend: host.docker.internal:3306
    |
    +-- Docker internal sandbox network
          |
          +-- sandbox-agent-*-agent_1 container
          |     entry agent
          |     calls company-header-agent:8080/a2a
          |
          +-- sandbox-agent-*-company_header_agent container
          |     network alias: company-header-agent
          |     A2A server on port 8080
          |
          +-- mcp-sidecar-* container
          |     network alias: mcp-sidecar
          |     MARIADB_HOST=haproxy-sidecar
          |
          +-- haproxy-sidecar-* container
          |     network alias: haproxy-sidecar
          |
          +-- squid proxy container
                network alias: egress-gateway
```

## Project Structure

```text
src/sandbox_agent/
  cli.py                       Host delegation and entry workload
  openai_agent.py              Entry OpenAI Agents SDK workload
  openai_tools.py              Entry OpenAI function-tool adapters
  sandbox_run.toml             Run-level multi-agent sandbox declaration
  sandbox_spec.toml            Entry agent declaration
  tools.py                     MCP calls, A2A client call, artifact saving

src/company_header_agent/
  a2a_server.py                Minimal A2A HTTP server
  cli.py                       Stdin/stdout and A2A server entry point
  openai_agent.py              Company header OpenAI Agents SDK workload
  openai_tools.py              Function-tool adapters
  sandbox_spec.toml            Supporting agent declaration
  tools.py                     MCP resource read and deterministic HTML injection

src/mcp_sidecar/
  audit.py                     JSONL audit logging
  cli.py                       MCP sidecar command-line entry point
  resources.py                 Local MCP resources
  server.py                    FastMCP server and exposure registry
  tools.py                     Local, MariaDB, Microsoft Learn, Jina, and code tools

src/docker_sandbox/
  cli.py                       Docker sandbox command-line orchestration
  container_factory.py         Docker image inspection and build
  landlock_runner.py           Linux Landlock path-policy launcher
  models.py                    Docker orchestration dataclasses
  run_results.py               Run artifact persistence
  sandbox_container.py         Containers, network, sidecars, artifacts, teardown
  sandbox_plan.py              Run/agent TOML parsing and resolved plan generation
  sandbox_spec.py              Capability validation and Dockerfile/profile generation

src/code_sidecar/
  runner.py                    Child-process script validator and runner
  server.py                    Internal HTTP service and result capture

src/sandbox_tester/
  Probe definitions and report generation used by --test-sandbox
```

## Notes

TwoAgentSandbox is a learning and hardening exercise, not a security proof. The
container policy reduces accidental host exposure and makes required capability
softening visible, but Docker, Landlock, seccomp, Squid, MCP tool boundaries,
A2A behavior, sidecar behavior, and Python runtime guards should not be
interpreted as a complete isolation guarantee.

Generated content can vary between runs because it is model-generated.

Run artifacts under `.docker_sandbox/runs` are ignored by Git.

## Third-Party Notices

This project uses third-party packages including `mcp`, `openai`,
`openai-agents`, `pillow`, and `pymysql`. It also uses Docker images such as
`python:3.12-slim`, `ubuntu/squid:latest`, `haproxy:latest`,
`ollama/ollama:latest`, and `ghcr.io/jina-ai/reader:oss`. See each package and
image license metadata for details.

## License

GNU General Public License v3.0. See the `LICENSE` file for details.

# TwoAgentSandbox

TwoAgentSandbox is a Python command-line project for running AI agents inside
hardened, disposable Docker containers on a shared Docker network.

The current default workload runs four agents:

- `writer_agent`: a supporting A2A agent. It creates structured movie JSON with
  a title, tagline, synopsis, genre, and visual style.
- `artist_agent`: a supporting A2A agent. It asks the MCP sidecar to generate
  one illustration from the movie details, writes it to the shared artifact
  volume, and returns compact artifact metadata.
- `poster_agent`: a supporting A2A agent. It uses the illustration as a
  reference image, asks the MCP sidecar to generate a final movie poster, writes
  it to the shared artifact volume, and returns compact artifact metadata.
- `sandbox_agent`: the entry agent. It asks `writer_agent` for movie details,
  asks `artist_agent` for the illustration, asks `poster_agent` for the final
  poster, and owns the final `index.html`, `illustration.png`, and `poster.png`
  artifacts.

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
6. It starts `writer_agent`, `artist_agent`, and `poster_agent` as supporting
   A2A HTTP services.
7. It runs `sandbox_agent` as the foreground entry agent.
8. `sandbox_agent` asks `writer_agent` for structured movie JSON.
9. `sandbox_agent` gives the movie JSON to `artist_agent`.
10. `artist_agent` calls the MCP tool `generate_image` to create one cinematic
    illustration, writes it under `/sandbox-shared/artist_agent/`, and returns
    compact artifact metadata.
11. `sandbox_agent` gives the movie JSON and illustration metadata to
    `poster_agent`.
12. `poster_agent` calls the MCP tool `generate_image` with the illustration as
    a reference image to create a complete movie poster containing the movie
    name, tagline, illustration, and poster-style design content. It writes the
    poster under `/sandbox-shared/poster_agent/` and returns compact artifact
    metadata.
13. `sandbox_agent` saves the generated illustration as
    `/sandbox-output/site/illustration.png`.
14. `sandbox_agent` saves the generated poster as
    `/sandbox-output/site/poster.png`.
15. `sandbox_agent` prepares an HTML document that displays both images and
    presents the movie title, tagline, synopsis, genre, and visual style.
16. `sandbox_agent` saves the HTML as `/sandbox-output/site/index.html` and
    writes `/sandbox-output/answer.txt`.
17. When the entry agent exits, the Docker network and containers are torn down.

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
  "../writer_agent/sandbox_spec.toml",
  "../artist_agent/sandbox_spec.toml",
  "../poster_agent/sandbox_spec.toml",
  "sandbox_spec.toml",
]

[execution]
mode = "entry_agent"
entry_agent = "agent_1"
order = [
  "writer_agent",
  "artist_agent",
  "poster_agent",
  "agent_1",
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
container_capabilities = [
  "network",
  "shared_volume",
]
application_capabilities = [
  "openai",
]
```

The run-level file owns shared network and appliance defaults. It also names all
agent spec files and defines the execution model. The `[mcp_sidecar]`
`container_capabilities` and `application_capabilities` arrays describe the MCP
server sidecar's own image and container requirements.

### Execution Mode

The default uses:

```toml
[execution]
mode = "entry_agent"
entry_agent = "agent_1"
```

In this mode, the entry agent is run as the foreground process. If a run declares
additional non-entry agents, those are started first as long-running supporting
HTTP agents. When the entry agent exits, the whole run is considered complete.

Sequential multi-agent execution is also supported by the planner/runtime. The
default project now uses the entry-agent model with two supporting A2A services.

## Agent Specs

Each agent declares its own container and application needs.

`src/sandbox_agent/sandbox_spec.toml` declares the entry agent:

```toml
schema_version = 1
agent_id = "agent_1"
module = "sandbox_agent"

container_capabilities = [
  "network",
  "shared_volume",
]

application_capabilities = [
  "image_artifacts",
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

`src/writer_agent/sandbox_spec.toml` declares the supporting writer agent:

```toml
schema_version = 1
agent_id = "writer_agent"
module = "writer_agent"

container_capabilities = [
  "network",
]

application_capabilities = [
  "openai_agents",
]

[mcp_sidecar]
tools = []
resources = []
```

`src/artist_agent/sandbox_spec.toml` declares the supporting artist agent:

```toml
schema_version = 1
agent_id = "artist_agent"
module = "artist_agent"

container_capabilities = [
  "network",
]

application_capabilities = [
  "mcp_client",
]

[mcp_sidecar]
tools = [
  "generate_image",
]
resources = []
```

`src/poster_agent/sandbox_spec.toml` declares the supporting poster agent:

```toml
schema_version = 1
agent_id = "poster_agent"
module = "poster_agent"

container_capabilities = [
  "network",
  "shared_volume",
]

application_capabilities = [
  "image_artifacts",
  "mcp_client",
]

[mcp_sidecar]
tools = [
  "generate_image",
]
resources = []
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

The current default run produces separate agent images because `sandbox_agent`,
`writer_agent`, `artist_agent`, and `poster_agent` declare different
application and sidecar requirements.

## Shared Sidecars

### Shared Artifacts

Agent containers that declare the `shared_volume` container capability receive a
read/write mount at:

```text
/sandbox-shared
```

The host-side source is a per-run directory:

```text
.docker_sandbox/runs/run-YYYY-mm-dd-HH-MM-SS/shared/
```

The default movie-poster workflow uses this for large image handoffs:
`artist_agent` writes `artist_agent/illustration.png` into the shared volume,
`poster_agent` reads that illustration as a reference image and writes
`poster_agent/poster.png`, and `sandbox_agent` copies both artifacts into its
own web output directory. This keeps large base64 image data out of
model-visible A2A/tool responses.

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
declared tools/resources. Its own run-level capabilities are declared in
`sandbox_run.toml` under `[mcp_sidecar]`. For example, `network` lets the MCP
sidecar join the sandbox network and use the Squid proxy, and `openai` installs
the `openai` Python package into the MCP sidecar image and passes
`OPENAI_API_KEY` from the host into the sidecar container.

Implemented MCP tools include:

- `get_html_element_name`
- `get_active_items`
- `generate_image`
- `microsoft_docs_search`
- `microsoft_docs_fetch`
- `microsoft_code_sample_search`
- `jina_read_url`
- `run_python_script`

Implemented MCP resources include:

- `answer_format`: `mcp-sidecar://instructions/answer-format.md`
- `company_name`: `mcp-sidecar://company/name.txt`

MCP tool/resource calls are audited in `mcp-sidecar-tool-calls.jsonl`.

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
      site/illustration.png
      site/poster.png
```

`resolved-sandbox-plan.json` is the best debugging artifact for image names,
container names, IP addresses, sidecar exposure, and generated ACL intent.

## Capabilities

Supported container/application capabilities include:

- `network`
- `shared_volume`
- `mcp_client`
- `image_artifacts`
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

The project has nine main packages:

- `a2a_support`: shared client and server helpers for the project's small A2A
  HTTP integrations, including Agent Card construction, JSON-RPC text messages,
  and response parsing.

- `sandbox_agent`: the entry workload. It owns the OpenAI Agents SDK prompt,
  Writer, Artist, and Poster Agent A2A calls, local artifact saving, and final
  page creation.
- `writer_agent`: the supporting OpenAI Agents SDK workload and small A2A HTTP
  server. It returns structured movie JSON for downstream poster generation.
- `artist_agent`: the supporting A2A workload that calls MCP `generate_image`,
  writes shared image artifacts, and returns compact artifact metadata.
- `poster_agent`: the supporting A2A workload that calls MCP `generate_image`
  with the illustration as a reference image, writes the final shared poster
  artifact, and returns compact artifact metadata.
- `mcp_sidecar`: the MCP server container workload. It owns local MCP resources,
  local MCP tools, OpenAI image generation, MariaDB access, Microsoft Learn
  proxy tools, Jina Reader client logic, code-execution client logic, and audit
  logging.
- `code_sidecar`: the optional no-network code-execution sidecar.
- `docker_sandbox`: the host/container harness. It owns TOML parsing, planning,
  per-agent image creation, Docker networking, sidecar startup, entry-agent
  execution, artifacts, and teardown.
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
          |     calls writer-agent:8080/a2a
          |     calls artist-agent:8080/a2a
          |     calls poster-agent:8080/a2a
          |
          +-- sandbox-agent-*-writer_agent container
          |     network alias: writer-agent
          |     A2A server on port 8080
          |
          +-- sandbox-agent-*-artist_agent container
          |     network alias: artist-agent
          |     A2A server on port 8080
          |     calls mcp-sidecar:8000/mcp
          |
          +-- sandbox-agent-*-poster_agent container
          |     network alias: poster-agent
          |     A2A server on port 8080
          |     calls mcp-sidecar:8000/mcp
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
src/a2a_support/
  client.py                    A2A Agent Card and message/send client helpers
  server.py                    A2A Agent Card and JSON-RPC response helpers

src/sandbox_agent/
  cli.py                       Host delegation and entry workload
  openai_agent.py              Entry OpenAI Agents SDK workload
  openai_tools.py              Entry OpenAI function-tool adapters
  sandbox_run.toml             Run-level multi-agent sandbox declaration
  sandbox_spec.toml            Entry agent declaration
  tools.py                     Writer/Artist/Poster A2A calls, MCP calls, and artifact saving

src/writer_agent/
  a2a_server.py                Minimal A2A HTTP server
  cli.py                       Stdin/stdout and A2A server entry point
  openai_agent.py              Movie JSON OpenAI Agents SDK workload
  sandbox_spec.toml            Supporting writer agent declaration

src/artist_agent/
  a2a_server.py                Minimal A2A HTTP server
  cli.py                       Stdin/stdout and A2A server entry point
  openai_agent.py              Movie illustration prompt and MCP image workflow
  sandbox_spec.toml            Supporting artist agent declaration
  tools.py                     MCP generate_image client wrapper

src/poster_agent/
  a2a_server.py                Minimal A2A HTTP server
  cli.py                       Stdin/stdout and A2A server entry point
  openai_agent.py              Poster prompt and MCP reference-image workflow
  sandbox_spec.toml            Supporting poster agent declaration
  tools.py                     MCP generate_image client wrapper

src/mcp_sidecar/
  audit.py                     JSONL audit logging
  cli.py                       MCP sidecar command-line entry point
  resources.py                 Local MCP resources
  server.py                    FastMCP server and exposure registry
  tools.py                     Local, OpenAI, MariaDB, Microsoft Learn, Jina, and code tools

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
sidecar behavior, and Python runtime guards should not be interpreted as a
complete isolation guarantee.

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

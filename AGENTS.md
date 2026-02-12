# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

**Hummingbot** is an open-source framework for designing and deploying automated trading strategies across centralized and decentralized exchanges. The repository is organized into three main components:

- **hummingbot/**: Main Python application (~14 subdirectories covering connectors, strategies, core infrastructure, and UI)
- **gateway/**: TypeScript-based middleware for DEX connectors (Uniswap, SushiSwap, etc.)
- **mcp/**: Python MCP server for AI integration with Hummingbot

## Development Environment

### Quick Setup
```bash
# Install conda environment and dependencies
make install

# Run tests
make test

# Run with optional Gateway
make setup  # answers a prompt about including Gateway
make deploy  # Docker-based deployment
```

### Alternative Manual Setup
```bash
conda env create -n hummingbot -f setup/environment.yml
conda run -n hummingbot conda develop .
conda run -n hummingbot python -m pip install --no-deps -r setup/pip_packages.txt
```

### Build & Test Commands

| Command | Purpose |
|---------|---------|
| `make install` | Creates/updates conda environment (`hummingbot`) from `setup/environment.yml` (or `setup/environment_dydx.yml` if `DYDX=1`), installs pip packages from `setup/pip_packages.txt`, installs pre-commit hooks, builds Cython extensions |
| `make test` | Runs pytest with coverage, excludes test directories for connectors not in active development |
| `make run_coverage` | Runs `make test` then generates HTML coverage report |
| `make development-diff-cover` | Compares coverage of changes against the `development` branch |
| `make build` | Builds Docker image (`hummingbot/hummingbot${TAG}`) |
| `make setup` | Interactive prompt to configure Gateway inclusion (sets `.compose.env`) |
| `make deploy` | Runs Docker Compose to deploy stack (uses `.compose.env` profile) |
| `make run` | Runs Hummingbot via `conda run -n hummingbot ./bin/hummingbot_quickstart.py` |
| `make down` | Stops Docker Compose with gateway profile |
| `make uninstall` | Removes the conda environment |
| `conda run -n hummingbot python -m pytest test/path/to/test.py` | Run a single test file |

### Running Single Tests
After activating the conda environment, run tests using pytest:
```bash
# Single test file
pytest test/hummingbot/connector/exchange/binance/test_binance_exchange.py

# Single test method
pytest test/hummingbot/connector/exchange/binance/test_binance_exchange.py::BinanceExchangeTests::test_some_method

# Run tests for a specific connector
conda run -n hummingbot pytest test/hummingbot/connector/exchange/binance/

# Run tests for a specific strategy
conda run -n hummingbot pytest test/hummingbot/strategy/pure_market_making/
```

### Code Quality & Linting

Pre-commit hooks are automatically installed via `make install`. Hooks include:
- **trailing-whitespace** and **end-of-file-fixer**: Whitespace cleanup
- **check-yaml** and **check-added-large-files**: Validation
- **flake8**: Python linting (max-line-length: 120, ignores: E251, E501, E702, W504, W503; extra ignores for `.pyx`/`.pxd` files)
- **autopep8**: Auto-formatting (`--select=E26,E114,E117,E128,E129,E201,E202,E225,E226,E231,E261,E301-E306,E401,W291-W293,W391`)
- **isort**: Import sorting (line-length: 120, `multi_line_output = 3`, trailing commas)
- **eslint**: JavaScript/TypeScript linting (for gateway code)
- **detect-private-key** and **detect-wallet-private-key**: Prevents committing secrets

Manual runs:
```bash
# Run all pre-commit hooks
conda run -n hummingbot pre-commit run --all-files

# Run specific linters
conda run -n hummingbot flake8 .
conda run -n hummingbot isort --settings-path=pyproject.toml --check-only --diff .
conda run -n hummingbot black --check .

# Auto-format code
conda run -n hummingbot autopep8 --in-place --max-line-length=120 --select=E26,E114,E117,E128,E129,E201,E202,E225,E226,E231,E261,E301,E302,E303,E304,E305,E306,E401,W291,W292,W293,W391 .
conda run -n hummingbot isort --settings-path=pyproject.toml .
conda run -n hummingbot black .

# TypeScript (gateway)
cd gateway && npm run lint
```

### Build Cython Extensions
```bash
conda run -n hummingbot python setup.py build_ext --inplace
```

## Code Style Guidelines

### Formatting
- Maximum line length: 120 characters (configured in .flake8, pyproject.toml)
- 4 spaces for indentation (no tabs)
- Unix-style line endings, files end with newline
- Remove trailing whitespace

### Imports
- Group: standard library → third-party → local application
- Use absolute imports when possible
- Sort alphabetically within each group (isort handles this)

### Naming Conventions
- `snake_case` for variables, functions, methods
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Prefix private/internal members with underscore (`_`)

### Type Hints
- Use type hints for function parameters and return values
- Use modern Python typing features (from typing module)

## Architecture Patterns

### Connector Architecture

Connectors standardize REST/WebSocket APIs to different exchanges. Three main types:

1. **Exchange Connectors** (`hummingbot/connector/exchange/`): Spot market trading
   - Examples: Binance, Coinbase, KuCoin
   - Base: `ExchangeBase` (Cython) and `ExchangePyBase` (Python)
   - Key files: `client_order_tracker.py`, `in_flight_order_base.pyx`

2. **Derivative Connectors** (`hummingbot/connector/derivative/`): Futures/perpetuals
   - Examples: Binance Perpetual, Bybit Perpetual
   - Base: `DerivativeBase`

3. **Gateway Connectors** (`hummingbot/connector/gateway/`): DEX connectors via Gateway middleware
   - Types: AMM routers (0x, Uniswap), AMM pools (Curve, SushiSwap), CLMM pools (Raydium)
   - Communicates with TypeScript Gateway service

**Key files shared across connectors:**
- `connector_base.pyx`: Base connector class (Cython for performance)
- `exchange_base.pyx`: Base for spot exchanges
- `perpetual_derivative_py_base.py`: Base for perpetual derivatives
- `budget_checker.py`: Validates orders against account limits
- `markets_recorder.py`: Records trading activity

### Strategy Architecture

Two strategy generations coexist:

1. **Strategy v1** (`hummingbot/strategy/`): Legacy, monolithic strategies
   - Examples: `pure_market_making/`, `cross_exchange_market_making/`
   - Each strategy has its own implementation
   - Use for reference; new strategies should use v2

2. **Strategy v2** (`hummingbot/strategy_v2/`): Modern, modular architecture
   - **Controllers** (`strategy_v2/controllers/`): Define trading logic independently of exchanges
   - **Executors** (`strategy_v2/executors/`): Execute controller signals on specific connectors
   - **Backtesting** (`strategy_v2/backtesting/`): Simulation framework
   - More maintainable and reusable across connectors

### Core Infrastructure

- **Events** (`core/event/`): Event-driven architecture (e.g., `BuyOrderCreatedEvent`, `SellOrderCompletedEvent`)
- **API Throttler** (`core/api_throttler/`): Rate limiting for exchange APIs
- **Data Types** (`core/data_type/`): Order, Trade, Market, Balance objects
- **Rate Oracle** (`core/rate_oracle/`): Fetches exchange rates for price conversion
- **Gateway** (`core/gateway/`): Communicates with the Gateway service
- **C++ Components** (`core/cpp/`): High-performance data structures (compiled)

### Client & UI

- **Commands** (`client/command/`): CLI commands (create_market_order, cancel_order, etc.)
- **UI** (`client/ui/`): Terminal UI using prompt_toolkit
- **Config** (`client/config/`): Configuration management for strategies and exchanges

## Important Development Notes

### Cython Compilation
- Performance-critical code is written in `.pyx` (Cython)
- Base classes use Cython: `connector_base.pyx`, `exchange_base.pyx`, `in_flight_order_base.pyx`
- C++ headers in `core/cpp/`
- Compilation happens during `make install` via `setup.py build_ext`
- Modify `.pyx` files → changes require reinstalling the environment or running `python setup.py build_ext --inplace`

### Testing Requirements
- **Minimum 80% unit test coverage** required for pull requests
- UI components are excluded from coverage validation
- Test structure mirrors `hummingbot/` in `test/hummingbot/`
- pytest uses `asyncio_default_fixture_loop_scope = "function"` — each async test gets its own event loop
- Use `coverage run` and `coverage html` for detailed reports
- Ignored test paths in `make test`: `test/mock/`, `ndax/`, `dydx_v4_perpetual/`, `remote_iface/`, `oms_connector/`, `amm_arb/`, `cross_exchange_market_making/`

### Data Models & ORM
- Uses SQLAlchemy for database interactions (`hummingbot/model/`)
- Database migrations in `model/`
- OrderBook, Trade, and Balance models defined in data types

### Logging
- Centralized logging in `hummingbot/logger/`
- Each module logs via logger mixin
- Log configuration in `templates/` (logging templates for config)

## Git Workflow

### Branch Naming
- `feat/...` - New features
- `fix/...` - Bug fixes
- `refactor/...` - Code improvements without behavior change
- `doc/...` - Documentation

### Commit Messages
Prefix each commit:
- `(feat)` - New feature
- `(fix)` - Bug fix
- `(refactor)` - Code refactor
- `(cleanup)` - Code cleanup
- `(doc)` - Documentation

Example: `(feat) add websocket support for Coinbase connector`

### Pull Request Process
1. Create branch from `development` (not from `master` or other feature branches)
2. Make commits with proper prefixes
3. Rebase upstream development: `git pull --rebase upstream development`
4. Push to your fork and create PR to upstream `development` branch
5. Ensure 80% test coverage for new code
6. Address reviewer feedback with new commits (don't amend)
7. Run `make development-diff-cover` locally to check coverage of your changes
8. Allow edits by maintainers

## Gateway (TypeScript)

Located in `gateway/` subdirectory. Key files:
- `package.json`: Dependencies and scripts
- `src/`: TypeScript source code for DEX connectors
- Uses Node.js and Express for HTTP API
- Has its own `CONTRIBUTING.md` and workflow

Install dependencies:
```bash
cd gateway
npm install
npm run build
npm run test
```

## MCP Server (Python)

Located in `mcp/` subdirectory. Enables AI assistants (Claude, Gemini) to interact with Hummingbot.
- `hummingbot_mcp/`: Main MCP server implementation
- `pyproject.toml`: Project configuration
- `main.py`: Entry point

Install:
```bash
cd mcp
pip install -e .
```

## IDE Configuration (VS Code/Cursor)

### Required Files

1. `.env`:
```
PYTHONPATH=${PYTHONPATH}:${PWD}
CONDA_ENV=hummingbot
```

2. `.vscode/settings.json`:
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "test",
        "--ignore=test/hummingbot/connector/derivative/dydx_v4_perpetual/",
        "--ignore=test/hummingbot/connector/derivative/injective_v2_perpetual/",
        "--ignore=test/hummingbot/connector/exchange/injective_v2/",
        "--ignore=test/hummingbot/remote_iface/",
        "--ignore=test/connector/utilities/oms_connector/",
        "--ignore=test/hummingbot/strategy/amm_arb/",
        "--ignore=test/hummingbot/client/command/test_create_command.py"
    ],
    "python.envFile": "${workspaceFolder}/.env",
    "python.terminal.activateEnvironment": true
}
```

3. `.vscode/launch.json`:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Hummingbot",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceRoot}/bin/hummingbot.py",
            "console": "integratedTerminal"
        }
    ]
}
```

## Common Tasks

### Adding a New Exchange Connector
1. Create folder in `hummingbot/connector/exchange/[exchange_name]/`
2. Implement classes inheriting from `ExchangePyBase` or `ExchangeBase`
3. Implement order placement, cancellation, status tracking
4. Add tests in `test/hummingbot/connector/exchange/[exchange_name]/`
5. Register in connector registry
6. Achieve 80% test coverage

### Adding a New Strategy v2
1. Create controller in `hummingbot/strategy_v2/controllers/[strategy_name]/`
2. Implement signal generation logic
3. Create executor in `hummingbot/strategy_v2/executors/`
4. Add backtesting support
5. Write comprehensive tests

## Special Considerations

1. Some tests are intentionally ignored due to known issues
2. Conda environment is required for proper dependency management
3. Cython extensions require special compilation steps
4. Gateway integration adds complexity for DEX connectors
5. Configuration files may be modified by tests (avoid running certain tests locally)

## References

- **Official Docs**: https://hummingbot.org/
- **Contributing**: See [CONTRIBUTING.md](./CONTRIBUTING.md)
- **IDE Setup**: See [CURSOR_VSCODE_SETUP.md](./CURSOR_VSCODE_SETUP.md)

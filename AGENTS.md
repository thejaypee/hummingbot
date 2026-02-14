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

### Error Handling
- Use specific exception types rather than generic exceptions
- Always include meaningful error messages
- Log errors appropriately using the centralized logging system
- Handle exceptions close to where they occur

### Documentation
- Document all public functions, classes, and modules with docstrings
- Follow Google Python Style Guide for docstrings
- Include type information in docstrings
- Document complex logic with inline comments

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

## Autonomous Multi-Token Trader

DEX-only autonomous trader using Uniswap V4 (UniversalRouter + Permit2). No CEX.

### Architecture

| File | Purpose |
|------|---------|
| `autonomous_trader.py` | Main orchestrator — hold-then-sell, TP/SL, multichain |
| `config/trading_config.py` | V4 contract addresses for 8 chains (5 mainnet + 3 testnet) |
| `token_registry.py` | SQLite cache for tokens + pools |
| `token_monitor.py` | ERC20 balance detection |
| `whitelist.py` | Sender whitelist + token auto-whitelist |
| `bot_api_server.py` | REST API (port 4000) — multi-token endpoints, emergency controls |
| `dashboard_server.py` | Serves dashboard (port 3000) |
| `dashboard.html` | STOP/SELL ALL buttons + multichain views |
| `start_trader.sh` | Launches API + Dashboard + Trader |

### Critical Rules — DO NOT VIOLATE

- **On-chain pool pricing ONLY**: Token prices come ONLY from the actual V3/V4 pool slot0 (sqrtPriceX96) on MAINNET. For testnet tokens, pricing reads from the corresponding mainnet pool. NEVER use any off-chain API for pricing.
- **No periodic scanning**: Wallet scan at startup only. Rescan after buys/sells. No polling, no periodic rescans, no watchers.
- **Testnet is for swaps only**: Testnet chains execute trades. Mainnet chains provide pricing data. Never read prices from testnet pools.
- **Pool discovery via V3 Factory on-chain only**: `discover_v3_pool()` uses `Factory.getPool()` on-chain. No external API for pool discovery.
- **DB persists at `data/token_registry.db`**: NOT in `/tmp/`. Survives reboots.
- **Gas reserve**: NEVER let native ETH drop below `GAS_RESERVE_ETH` (0.01) on any chain.
- **Whitelisted sender**: `0xef63f3aB80525d12C628038f37C32c4E108969F6`

### How It Works

1. Startup: scan `alchemy_getAssetTransfers` for tokens sent to wallet from whitelisted senders
2. For each found token with balance: discover pool on-chain via V3 Factory
3. Record HOLD position with entry price from mainnet pool slot0
4. Monitor TP/SL (2%/2% default) using mainnet pool prices
5. Exit via UniversalRouter V4 swap on the token's chain

### Running

```bash
bash start_trader.sh        # starts everything
tail -f /tmp/trader.log     # watch output
touch /tmp/trader_stop      # emergency stop
touch /tmp/trader_sell_all  # sell all positions
```

### Uniswap V4 Details (official docs only)

- Command: `V4_SWAP = 0x10`
- Actions: `SWAP_EXACT_IN_SINGLE=6, SETTLE_ALL=12, TAKE_ALL=15`
- Permit2: `0x000000000022D473030F116dDEE9F6B43aC78BA3` (same all chains)
- `execute(bytes commands, bytes[] inputs, uint256 deadline)`
- PoolManager.getSlot0(poolId) for on-chain pricing via sqrtPriceX96

## Special Considerations

1. Some tests are intentionally ignored due to known issues
2. Conda environment is required for proper dependency management
3. Cython extensions require special compilation steps
4. Gateway integration adds complexity for DEX connectors
5. Configuration files may be modified by tests (avoid running certain tests locally)
6. **Module waitlist**: See `MODULE_WAITLIST.md` for planned features and development roadmap

## References

- **Official Docs**: https://hummingbot.org/
- **Contributing**: See [CONTRIBUTING.md](./CONTRIBUTING.md)
- **IDE Setup**: See [CURSOR_VSCODE_SETUP.md](./CURSOR_VSCODE_SETUP.md)
- **Module Roadmap**: See [MODULE_WAITLIST.md](./MODULE_WAITLIST.md)

# Volt Interpreter

Volt is a schematic-inspired language with explicit memory lifecycle control.
The implementation is in `interpreter/` and is built with TextX.

## Core Guarantees

- **Explicit allocation/deallocation**: variables are created only via `VoltageSource -> CapacitorStore` and released via `_|_`.
- **Compile-time leak rejection**: static analysis is path-sensitive and rejects programs where any allocated source can survive termination on any control-flow path.
- **No GC dependency**: runtime does not rely on garbage collection for language memory lifecycle.
- **Physically constrained memory**: integer writes are bounded by signed/unsigned bit width (including non-byte-aligned widths like `9v`).
- **Deterministic cleanup on faults**: runtime always clears remaining allocations on termination, including errors.

## Repository Layout

- `interpreter/volt.tx` - grammar
- `interpreter/interpreter.py` - execution engine + static analysis
- `sample_programs/` - example Volt programs
- `tests/test_engine.py` - regression/edge-case suite
- `run_tests.sh` - one-command test runner

## Requirements

- Python 3.9+
- `textX`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install textX
```

## Run a Program

From repo root:

```bash
cd interpreter
python3 interpreter.py ../sample_programs/hello_world.volt
```

## Run All Tests (TA/Demo)

```bash
./run_tests.sh
```

## Language Snapshot

### Trace Shape

Every statement is a left-to-right trace:

```volt
start_expression ===> pipe ===> pipe ===> ... ;
```

Trace must terminate at:

- `|| variable_name` (store/continue using an allocated variable), or
- `_|_` (ground/deallocate active source)

### Memory Declaration Model

Variable identity lives in `CapacitorStore` only:

```volt
"admin" ===> [+40v-] ===> || username ;
```

- `[+Nv-]` = unsigned `N`-bit storage
- `[-Nv+]` = signed `N`-bit storage

### Operations

- Print: `(O)`
- Math: `(+)`, `(-)`, `(%)`
- Logic: `(=)`, `(>)`, `(<)`
- Bool literals: `[^]` (high/true), `[v]` (low/false)

### Control Flow

```volt
(~)[5v] { ... }                 // loop
_/_[condition] { [^]: ... [v]: ... }   // branch
```

Branch conditions must evaluate to bool signals (`[^]`/`[v]`).

## Example (Current Syntax)

```volt
5v ===> [-8v+] ===> || signed_counter ;
signed_counter ===> (-) 10v ===> || signed_counter ;
"Signed result (8-bit):" ===> (O) ===> _|_ ;
signed_counter ===> (O) ===> || signed_counter ;
signed_counter ===> _|_ ;
```

## Notes

- This implementation emphasizes strict lifecycle and constrained-memory semantics.
- See `tests/test_engine.py` for full expected behavior, including failure cases.

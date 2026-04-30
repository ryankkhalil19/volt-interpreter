# Volt Interpreter

Core execution engine for the Volt programming language.

Volt is a strictly typed, schematic-inspired language where data must flow through explicit traces and physically terminate at Ground (`_|_`). This interpreter implements the Phase 1 execution model using TextX with a strict left-to-right, 1D pipeline.

## Why this design works
- Enforces **explicit flow**: all operations occur in `Trace` pipelines.
- Enforces **hard termination**: every trace must end with `_|_` in grammar.
- Enforces **memory safety by structure**: open or incomplete traces fail parse-time.
- Enforces **capacity checks**: voltage overflow on capacitor declarations throws runtime errors.

## Repository structure
- `volt.tx` - TextX grammar for Volt syntax and control structures.
- `interpreter.py` - Semantic execution engine (evaluation + runtime validation).
- `README.md` - Project documentation, setup, and examples.

## Requirements
- Python 3.9+
- `textX`

## Installation
Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install textX
```

If you prefer global install:

```bash
pip3 install textX
```

## Running the interpreter
```bash
python3 interpreter.py path/to/program.volt
```

## Example Volt program
Create `example.volt`:

```volt
5v ===> ||[10v] capA ===> Add 3v ===> [=][PrintNode] ===> _|_;
(~)[2v]{
  1v ===> Add 1v ===> [=][PrintNode] ===> _|_;
}
```

Run:

```bash
python3 interpreter.py example.volt
```

## Safety model
Volt's safety guarantees in this phase come from two layers:

1. **Grammar safety (parse-time):** missing `_|_` makes the source invalid.
2. **Execution safety (runtime):** uninitialized references and capacitor overloads raise immediate errors.

## Roadmap
- Add richer node types (I/O, typed arithmetic families).
- Improve diagnostics with line/column-aware runtime errors.
- Reintroduce multidirectional schematic semantics on top of validated core pipeline behavior.

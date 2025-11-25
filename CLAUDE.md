## Development Commands

This project uses `uv` as the package manager.

**Run the example**:
```bash
uv run python examples/calculator_agent/optimise_agent.py
```

**Tree cmd for exapanding dirs**
`tree` is installed and you can use it to explore dirs etc.

## How to work
- Exploration is often key to understanding the task at hand, so even if directed to a single file, feel free to explore related files if they will help you better understand the task at hand.

- Only add docstrings if the function is sufficiently complex. Instead strive for readable code clean code practices.


## Clean code
- Instead of using dicts for passing data around (except where relevant), prefer dataclasses or pydantic BaseModels for type safety reasons.
- Instead of writing the same string in multiple related places in a single file/class etc, prefer to use a shared variable
- Use proper type hints from the `typing` module wherever relevant (e.g., `Optional[str]`, `list[str]`, `dict[str, Any]`, `Callable[[Args], ReturnType]`)

## Architecture patterns
- **Prefer abstraction and dependency injection**: When adding new functionality, especially cross-cutting concerns, create abstract base classes that define interfaces and inject concrete implementations through constructor parameters.
  - Abstract base classes should use ABC and @abstractmethod to define contracts
  - Concrete implementations should be pluggable and swappable
  - Use optional parameters with `None` defaults for backward compatibility
  - This allows flexibility to change implementations without modifying core code
  - Users can provide custom implementations suited to their needs
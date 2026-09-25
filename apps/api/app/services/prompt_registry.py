"""Versioned local prompt registry for typed Rizzo decisions."""
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PromptDefinition:
    name: str
    version: str
    path: Path

    def read(self) -> str:
        """Read the registered prompt body only when an execution needs it."""
        return self.path.read_text()


def get_prompt(name: str, version: str = "v1") -> PromptDefinition:
    """Resolve an audited prompt definition from the local prompt volume."""
    path = Path("/prompts") / name / f"{version}.md"
    if not path.is_file():
        raise ValueError("Prompt definition is not registered locally.")
    return PromptDefinition(name=name, version=version, path=path)

"""
dialectic_ai/core/dialectical.py

DIALECTICAL DESCRIPTION:
  Origin: The developer writes classes that do not explain
    WHY they exist — only WHAT they do. Knowledge is lost.
  Contradiction: The code grows, but its philosophical genesis remains invisible.
    A new developer (or the author themselves after a month) does not understand the logic of the system.
  How it solves: Introduces a standard decorator @dialectical, which attaches
    a structured philosophical description to any class. This decorator
    does not affect the behavior of the class but makes its history readable by machines.
  What it leads to: DevelopmentLogger can collect these descriptions and build
    a "dialectical map" of the entire project. The CLI command `dialectic map` can
    draw a graph of dependencies with philosophical comments.
  Its own contradictions: The decorator adds a disciplinary burden —
    the developer is OBLIGED to fill it out. Without enforcement, it will remain
    a recommendation rather than a law of the framework.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DialecticalMetadata:
    """Structure of the dialectical description of any component."""
    origin: str          # Origin / what void it fills
    contradiction: str   # What contradiction / problem it solves
    resolves: str        # How it specifically resolves
    generates: str       # What it generates in the next step (outflow)
    own_contradictions: str  # What contradictions it itself enters
    layer: int = 0       # Layer of the framework (0-6)
    name: str = ""       # Automatically filled from the class
    # Rule 5 (dialectics_rules.md) fields — optional, filled only for components that went
    # through the full "Simplest -> Development -> Opposite -> Contradiction -> Leap" procedure.
    # Left empty by default so all pre-existing @dialectical(...) call sites stay valid unchanged.
    simplest_process: str = ""   # The generative simplest process this component's origin reduces to
    opposite_process: str = ""   # A process whose development does NOT require this component to exist


# Global registry of all dialectically described components
_DIALECTICAL_REGISTRY: list[DialecticalMetadata] = []


def dialectical(
    origin: str,
    contradiction: str,
    resolves: str,
    generates: str,
    own_contradictions: str,
    layer: int = 0,
    simplest_process: str = "",
    opposite_process: str = "",
):
    """
    Decorator that attaches a dialectical description to a class.

    Usage:
        @dialectical(
            origin="...",
            contradiction="...",
            resolves="...",
            generates="...",
            own_contradictions="...",
            layer=0,
        )
        class MyClass:
            ...
    """
    def decorator(cls):
        meta = DialecticalMetadata(
            origin=origin,
            contradiction=contradiction,
            resolves=resolves,
            generates=generates,
            own_contradictions=own_contradictions,
            layer=layer,
            name=cls.__name__,
            simplest_process=simplest_process,
            opposite_process=opposite_process,
        )
        # Attach metadata to the class
        cls.__dialectical__ = meta
        # Register globally for map building
        import logging
        existing = next((m for m in _DIALECTICAL_REGISTRY if m.name == cls.__name__), None)
        if existing:
            logging.warning(f"Dialectical component '{cls.__name__}' is being re-registered. Replacing the old entry.")
            _DIALECTICAL_REGISTRY.remove(existing)
            
        _DIALECTICAL_REGISTRY.append(meta)
        return cls
    return decorator


def get_dialectical_map() -> list[DialecticalMetadata]:
    """Returns all registered components, sorted by layers."""
    return sorted(_DIALECTICAL_REGISTRY, key=lambda m: m.layer)


def print_dialectical_card(cls) -> None:
    """Prints the dialectical card of the class to the console."""
    meta: Optional[DialecticalMetadata] = getattr(cls, "__dialectical__", None)
    if not meta:
        print(f"[!] {cls.__name__} does not have a dialectical description.")
        return

    print(f"\n{'='*60}")
    print(f"  DIALECTICAL CARD: {meta.name}  (Layer {meta.layer})")
    print(f"{'='*60}")
    print(f"  📍 Origin:\n     {meta.origin}")
    print(f"\n  ⚡ The contradiction it solves:\n     {meta.contradiction}")
    print(f"\n  [OK] How it resolves:\n     {meta.resolves}")
    print(f"\n  ➡️  What it leads to (generates):\n     {meta.generates}")
    print(f"\n  🔄 Its own contradictions:\n     {meta.own_contradictions}")
    if meta.simplest_process:
        print(f"\n  🌱 Simplest process (Rule 5):\n     {meta.simplest_process}")
    if meta.opposite_process:
        print(f"\n  ⚔️  Opposite process (Rule 5):\n     {meta.opposite_process}")
    print(f"{'='*60}\n")


import sys


class DialecticalArchitectureError(Exception):
    pass

def custom_excepthook(exc_type, exc_value, traceback):
    if issubclass(exc_type, DialecticalArchitectureError):
        print("\n" + "="*80)
        print("🛑 ARCHITECTURAL ERROR (DIALECTIC-AI)")
        print("="*80)
        print(f"{exc_value}")
        print("="*80 + "\n")
        sys.exit(1)
    else:
        sys.__excepthook__(exc_type, exc_value, traceback)


def install_dialectical_excepthook() -> None:
    """
    Installs custom_excepthook as the process-wide sys.excepthook, for the nicer
    traceback formatting on DialecticalArchitectureError.

    Explicit opt-in, called by the CLI entry point (cli/main.py) -- NOT run as an
    import-time side effect of this module. Merely `import`ing this module used to
    silently rewrite the global exception hook for every importer, which is
    surprising for anyone embedding the framework inside a larger application with
    its own exception handling (see CODE_REVIEW.md, Layer 0). Call this yourself if
    you want the formatting outside the CLI.
    """
    sys.excepthook = custom_excepthook


class DialecticalObject:
    """
    Base class for ALL components of the framework.
    Guarantees physical compliance with Rule 1 (Generative Beginning).
    If a child class does not have the @dialectical decorator, object creation will result in an error.
    """
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "__dialectical__"):
            raise DialecticalArchitectureError(
                f"VIOLATION OF RULE 1: Class {cls.__name__} does not have a dialectical justification!\n\n"
                f"The developer of this class is obliged to use the @dialectical decorator above the class,\n"
                f"to fix the origin, contradiction, and resolves. Without this, the architectural\n"
                f"component will not start. If {cls.__name__} is a built-in class of the framework, "
                f"please create an Issue on GitHub."
            )
        return super().__new__(cls)

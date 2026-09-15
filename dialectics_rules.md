# Dialectical Construction of AI Agents: Rules and Practices

In this document, we gather the principles, rules of inference, and best practices for building AI agents using the dialectical method. The document is supplemented as we communicate and learn.

## Core Principles

1. **Generative Dialectical Principle:** The essence of development lies in choosing the simplest first step (Point 1), which not only precedes the others but also generates them. 
   - Point 1 generates Point 2.
   - Points (1 + 2) generate Point 3.
   The system develops organically: from the simplest to the complex, accumulating history (state) and logically deriving each new entity from the entirety of previous steps.

2. **Continuous Meta-Learning of the Developer:** The process of creating an agent is akin to the process of constant human learning. We learn not only to write code but also to critically rethink each of our steps, every mistake, and every stage of architectural growth, constantly aligning with the external experience of humanity.

## Rules of Inference

1. **Principle of Inheritance of Properties (Derivation):** Each subsequent step of development must organically derive from the previous one, inheriting its features and limitations. (For example: the logic of the input mechanism is dictated by the system prompt device).

2. **Confrontation with the World (Practice and Correction):** Each significant step of development must be immediately checked against reality (launch, simulation). 
   - *Integration of Best Practices:* As soon as the confrontation with reality reveals a problem or failure, we address it while simultaneously aligning with the "best practices" from the industry. We critically evaluate these practices and consciously decide whether to apply them to solve our problem or not.

3. **Evaluation of the Transition Itself (Reflection on the Leap):** When transitioning to a fundamentally new architectural step (for example, from interaction logic to Memory architecture), it is necessary to pause and evaluate *the very nature of this transition*. Is this transition actually being made? What external practices and paradigms exist for this stage? We validate not only the code but also the direction of our thought.

4. **Development Memory (Keeping a Log):** Development must have its own continuous memory. From the first step, a lightweight log of architectural decisions is maintained. When starting each new step, it is necessary to refer not only to these rules of dialectics but also to the development log, to align the current vector with the history of previous steps.

5. **Driving to Contradiction (Simplest → Development → Opposite → Contradiction → Leap):** For *significant* steps (the same threshold as Rule 3 — a fundamentally new architectural step, not routine work), development must be pushed all the way to an explicit contradiction and its resolution, not stopped at "a problem and a fix."
   - **Simplest process:** the process that is (a) connected to the task at hand, (b) generative — the full set of developing processes can be approached starting from it, and (c) such that every developing process it generates is itself connected back to it.
   - **Development:** proceeds from abstract to concrete — each subsequent process is already contained in the previous one in potential form, and the previous one becomes more definite once the next one appears. This is *becoming*, not mere succession: a step must show one process turning into another, not just one placed next to another (see the distinction in point 7 below).
   - **Opposite process:** among the developing processes, one is found whose own development does **not require** the existence of the simplest process. "Does not require" is not "destroys" — it means the opposite process can fully develop without the simplest one. This is a different thing from an *alternative practice* (e.g., comparing `asyncio` vs `trio` vs `anyio` for the same problem, as already done under Rule 2/3) — an alternative practice competes to solve the *same* need; an opposite process does not need that need at all.
   - **Contradiction:** the simplest process and the opposite process, taken together in the unity of their development.
   - **Leap:** the process that resolves the contradiction — either a new process that replaces both, absorbing them into its own development, or a process that makes it possible for the contradiction to keep existing until it is resolved by such a replacing process. The leap can and should be explained, but only *as* the resolution of the contradiction, not derived from either side alone.
   - **Evidence criterion (for the Auditor and for self-review):** a `development_log.md` entry for a significant step must name the simplest process, show the development chain, name the opposite process specifically (not an alternative practice), state the contradiction as their unity, and name the leap. A step that only shows "problem → chosen fix" without these five elements has not been driven to contradiction — it is Rule 1–3 work, useful but not yet Rule 5 work.
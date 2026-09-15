"""
tests/test_gaia2_adapter.py

DIALECTICAL DESCRIPTION:
  Origin: AREToolWrapper.parameters() classified argument types with an if/elif chain
    that checked "str" in arg_type before "list" in arg_type. ARE reports list
    arguments as the string "list[str] | none" -- which contains "str" as a
    substring -- so every list[str] argument (recipients, cc, attendees, ...) was
    silently misclassified as a plain "string", disabling the array-coercion code
    that was already written (and already correct) for exactly this case.
  Contradiction: This was the single highest-impact bug found during this project's
    GAIA2 benchmarking (it broke email/calendar-attendee tool calls on nearly every
    scenario, in every run, for the whole session) -- yet it is also, in hindsight,
    a one-line ordering mistake that any test built against the real ARE tool schema
    would have caught immediately. It went unnoticed because the existing test suite
    tests AREToolWrapper (if at all) against hand-written fixtures, not the real
    ARE app classes whose actual type-string format is the whole crux of the bug.
  How it resolves: A direct assertion against the real `are.simulation` EmailClientApp,
    not a fixture -- so it keeps testing the actual thing that broke, and would also
    catch a *future* change in ARE's own type-string format that reintroduces the
    same class of bug in a new guise.
  What it leads to: If this if/elif ordering (or ARE's type-string format) ever
    regresses, this test fails immediately and specifically, instead of silently
    degrading GAIA2 scenario success rates the way the original bug did for an
    entire session before being caught by manual inspection.
  Own contradictions: Depends on the `are.simulation` package being installed and
    EmailClientApp's schema staying reasonably stable; if ARE renames send_email's
    arguments, this test needs updating too, not just the production code.
"""
from benchmarks.gaia2.adapter import AREToolWrapper


def _send_email_wrapper() -> AREToolWrapper:
    from are.simulation.apps.email_client import EmailClientApp

    app = EmailClientApp()
    tool = next(t for t in app.get_tools() if "send_email" in t.name)
    return AREToolWrapper(tool)


def test_list_str_arguments_are_classified_as_array_not_string():
    """The bug: 'list[str] | none' contains 'str' as a substring, so a naive
    if/elif chain checking scalar types before container types misclassifies
    every list argument as a plain string, silently disabling array coercion."""
    schema = _send_email_wrapper().parameters()
    for arg_name in ("recipients", "cc", "attachment_paths"):
        arg_schema = schema["properties"][arg_name]
        assert arg_schema["type"] == "array", (
            f"'{arg_name}' should be classified as 'array' (it is list[str] in ARE's own "
            f"schema), got {arg_schema['type']!r} -- this is exactly the type-classification "
            f"regression that broke recipients/cc/attendees on nearly every GAIA2 scenario "
            f"this session; see development_log.md, 2026-09-14."
        )


async def test_list_str_string_argument_is_coerced_to_a_one_element_list():
    """End-to-end: a tool call passing a single string for a list[str] argument
    (the shape an LLM naturally produces for "one recipient") must succeed via
    coercion, not fail with a type error."""
    wrapper = _send_email_wrapper()
    evidence = await wrapper.execute({
        "recipients": "someone@example.com",
        "subject": "test",
        "content": "hello",
    })
    assert evidence.success, (
        f"Expected the single-string 'recipients' value to be coerced into a "
        f"one-element list and the call to succeed; got error: {evidence.error!r}"
    )

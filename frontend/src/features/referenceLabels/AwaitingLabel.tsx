// Where an Episode's outputs would show before it has a Reference label: the server withholds
// them until then, so labels stay blind.

export function AwaitingLabelTag() {
  return (
    <span
      data-testid="awaiting-label"
      className="text-xs whitespace-nowrap text-muted-foreground italic"
    >
      Awaiting Reference label
    </span>
  );
}

export function AwaitingLabelNote() {
  return (
    <section aria-label="Triage">
      <AwaitingLabelTag />
      <p className="mt-1 text-sm text-muted-foreground">
        Its Triage decision, Reason and Criterion results stay hidden until it has a Reference
        label, so that label is given blind.
      </p>
    </section>
  );
}

// The Description cut into pieces to tint: each Phrase (by its index), each meaningful word no
// Phrase covers, and the plain text between them.

export interface Span {
  start: number;
  end: number;
}

export interface Segment {
  text: string;
  phrase?: number;
  uncovered?: true;
}

export function descriptionSegments(
  description: string,
  phrases: readonly Span[],
  uncovered: readonly Span[],
): Segment[] {
  const marks = [
    ...phrases.map((span, phrase) => ({ ...span, mark: { phrase } })),
    ...uncovered.map((span) => ({ ...span, mark: { uncovered: true as const } })),
  ].sort((a, b) => a.start - b.start);
  const segments: Segment[] = [];
  let at = 0;
  for (const { start, end, mark } of marks) {
    if (start < at) continue; // overlaps the one before; the server never sends these
    if (start > at) segments.push({ text: description.slice(at, start) });
    segments.push({ text: description.slice(start, end), ...mark });
    at = end;
  }
  if (at < description.length) segments.push({ text: description.slice(at) });
  return segments;
}

/** The clip a visual Criterion asked Spark about, served by the backend. */
export function visualClipUrl(episodeId: string, name: string): string {
  return `/api/episodes/${encodeURIComponent(episodeId)}/visual-clips/${name}`;
}

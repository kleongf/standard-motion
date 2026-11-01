import { useMutation } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type VoiceTurn = components["schemas"]["VoiceTurn"];
export type VoiceChip = components["schemas"]["VoiceChip"];

/** Send one push-to-talk turn: its transcript, and the unsure Phrases it decides, come back.
 * Nothing is saved until a chip is confirmed. */
export function useVoiceTurn() {
  return useMutation({
    mutationFn: async ({ episodeId, wav, t }: { episodeId: string; wav: Blob; t: number }) => {
      const { data, error, response } = await api.POST("/api/episodes/{episode_id}/voice", {
        params: { path: { episode_id: episodeId } },
        // The schema types a file part as a string; the form carries the WAV itself.
        body: { audio: "", t },
        bodySerializer: () => {
          const form = new FormData();
          form.append("audio", wav, "turn.wav");
          form.append("t", String(t));
          return form;
        },
      });
      if (!response.ok || !data) {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        throw new Error(typeof detail === "string" ? detail : "The turn couldn't be heard");
      }
      return data;
    },
  });
}

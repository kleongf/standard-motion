import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import type { components } from "../../api/schema";

export type ReviewQueue = components["schemas"]["ReviewQueue"];
export type ReviewItem = components["schemas"]["ReviewItem"];

export const reviewKey = ["review"] as const;

/** The Needs review Episodes, strictly least confident first, each with its unsure Phrases. */
export function useReviewQueue() {
  return useQuery({
    queryKey: reviewKey,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/review");
      if (!response.ok || !data) throw new Error(`Review queue failed: ${String(response.status)}`);
      return data;
    },
  });
}

import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";

/** What an export would decide on: every Episode outside the Test set, and how many of them
 * aren't Reference-labelled yet. Read on demand, when Export is pressed. */
export function useExportScope() {
  return useQuery({
    queryKey: ["export", "scope"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/export/scope");
      if (!response.ok || !data) {
        throw new Error(`Export scope failed: ${String(response.status)}`);
      }
      return data;
    },
    enabled: false,
  });
}

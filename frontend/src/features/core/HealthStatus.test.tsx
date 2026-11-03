import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { HealthStatus } from "./HealthStatus";

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderWithQuery() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <HealthStatus />
    </QueryClientProvider>,
  );
}

test("shows nothing once the backend answers", async () => {
  const fetch = vi.fn(() =>
    Promise.resolve(Response.json({ status: "ok", meta_api_key_configured: true })),
  );
  vi.stubGlobal("fetch", fetch);
  renderWithQuery();

  await waitFor(() => {
    expect(screen.queryByText("Connecting to backend…")).not.toBeInTheDocument();
  });
  expect(fetch).toHaveBeenCalled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("reports an unreachable backend", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(null, { status: 502 }))),
  );
  renderWithQuery();

  expect(await screen.findByRole("alert")).toHaveTextContent("Backend unreachable");
});

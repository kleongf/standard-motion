import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { EPISODES, ingest } from "./helpers.ts";

interface Preview {
  sources: Record<string, number | string>[];
  exported: number;
}

// Export writes every Episode outside the Test set by its Triage decision. This spec's Episode is
// never Reference-labelled, so the preview counts it as awaiting a label, and Export warns that it
// would show its decision before going ahead.
test("Export previews its counts, writes Keep + Needs review, and lists the export", async ({
  page,
  request,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await ingest(request, EPISODES.export);
  const preview = async (include: string) =>
    (await (await request.get(`/api/export/preview?include=${include}`)).json()) as Preview;

  await page.goto("/?page=export");
  const table = page.getByRole("table", { name: "Export preview" });
  const row = table.getByRole("row").filter({ hasText: "droid_100" });
  const keep = (await preview("keep")).sources.find((s) => s.source === "droid_100");
  expect(keep).toBeDefined();
  expect(Number(keep?.awaiting_label)).toBeGreaterThanOrEqual(1);
  const cells = ["keep", "needs_review", "reject", "awaiting_label", "test_set"].map((k) =>
    String(keep?.[k]),
  );
  await expect(row.getByRole("cell")).toHaveText(["droid_100", ...cells, cells[0] ?? ""]);
  await expect(page.getByTestId("export-unlabelled")).toContainText(
    /\d+ Episodes? (aren’t|isn’t) Reference-labelled yet\./,
  );

  await page.getByRole("radio", { name: /Keep \+ Needs review/ }).click();
  const both = await preview("keep_and_review");
  await expect(page.getByTestId("export-writes")).toContainText(
    `Writes ${String(both.exported)} Episode`,
  );
  await page.getByRole("button", { name: "Export", exact: true }).click();
  const warning = page.getByRole("alertdialog", { name: "Export before labelling?" });
  await warning.getByRole("button", { name: "Export anyway" }).click();

  const written = page.getByTestId("export-written");
  await expect(written).toContainText(
    /\d+ Episodes? \(\d+ Keep, \d+ Needs review\), and the Reasons for/,
    {
      timeout: 60_000,
    },
  );
  const path = (await written.locator("code").textContent()) ?? "";
  expect(path).toMatch(/\/exports\/[\w-]+$/);
  await written.getByRole("button", { name: `Copy ${path}` }).click();
  await expect(written.getByRole("button", { name: `Copy ${path}` })).toHaveText("Copied");

  const manifest = JSON.parse(readFileSync(join(path, "manifest.json"), "utf8")) as {
    include: string;
    exported: unknown[];
  };
  expect(manifest.include).toBe("keep_and_review");
  const past = page.getByRole("table", { name: "Past exports" }).getByRole("row").nth(1);
  await expect(past).toContainText(path);
  await expect(past).toContainText("Keep + Needs review");
  await expect(past.getByRole("cell").nth(2)).toHaveText(String(manifest.exported.length));
  await expect(page.getByRole("button", { name: "Export", exact: true })).toBeEnabled();
  expect(errors).toEqual([]);
});

import { expect, test } from "@playwright/test";

import { EPISODES, ingest } from "./helpers.ts";

// Export writes every Episode outside the Test set by its Triage decision. This spec's Episode is
// never Reference-labelled, so Export warns that it would show its decision before going ahead.
test("Export warns about unlabelled Episodes, then writes them and says where", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  await ingest(request, EPISODES.export);

  await page.goto("/?page=episodes");
  await page.getByRole("button", { name: "Export", exact: true }).click();

  const warning = page.getByRole("alertdialog", { name: "Export before labelling?" });
  await expect(warning).toContainText(
    /\d+ Episodes? (aren’t|isn’t) Reference-labelled yet\. Exporting shows/,
  );
  await warning.getByRole("button", { name: "Export anyway" }).click();

  const written = page.getByTestId("export-written");
  await expect(written).toContainText(
    /Exported \d+ kept Episodes?, and the Reasons for \d+ not kept \(\d+ of the \d+ not Reference-labelled yet\), to \S+\/exports\/\S+/,
    { timeout: 30_000 },
  );
  await expect(page.getByRole("button", { name: "Export", exact: true })).toBeEnabled();
  expect(errors).toEqual([]);
});

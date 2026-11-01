import { expect, test } from "vitest";

import { resolveTheme } from "./theme";

test("an explicit theme ignores the OS", () => {
  expect(resolveTheme("light", true)).toBe("light");
  expect(resolveTheme("dark", false)).toBe("dark");
});

test("system follows the OS", () => {
  expect(resolveTheme("system", true)).toBe("dark");
  expect(resolveTheme("system", false)).toBe("light");
});

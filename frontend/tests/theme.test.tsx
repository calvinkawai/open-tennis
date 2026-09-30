import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { ThemeToggle } from "../src/components/theme-toggle";
import { THEME_KEY, themeScript } from "../src/lib/theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

it("switches to the dark reading mode and remembers the choice", async () => {
  render(<ThemeToggle />);
  await userEvent.click(screen.getByRole("button", { name: "切换到深色阅读" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  await userEvent.click(screen.getByRole("button", { name: "切换到浅色" }));
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("restores a saved dark preference before the page paints", () => {
  localStorage.setItem(THEME_KEY, "dark");
  new Function(themeScript)();
  expect(document.documentElement.dataset.theme).toBe("dark");
});

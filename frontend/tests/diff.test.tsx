import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { VersionDiff } from "../src/components/version-diff";
import { diffParagraphs } from "../src/lib/diff";

it("reports removed and added paragraphs between versions", () => {
  expect(diffParagraphs("开头\n\n旧说法\n\n结尾", "开头\n\n新说法\n\n结尾\n\n补充")).toEqual([
    { kind: "same", text: "开头" },
    { kind: "removed", text: "旧说法" },
    { kind: "added", text: "新说法" },
    { kind: "same", text: "结尾" },
    { kind: "added", text: "补充" },
  ]);
});

it("ignores blank-line differences", () => {
  expect(diffParagraphs("a\n\nb", "a\n\n\n  \nb")).toEqual([{ kind: "same", text: "a" }, { kind: "same", text: "b" }]);
});

it("shows only the paragraphs that changed", () => {
  render(<VersionDiff before={"开头\n\n旧说法"} after={"开头\n\n新说法"} fromLabel="v3" toLabel="v4" />);
  const region = screen.getByRole("region", { name: "v3 → v4 的差异" });
  expect(within(region).getByText("新增 1 段")).toBeVisible();
  expect(within(region).getByText("旧说法").closest(".diff-block")).toHaveClass("removed");
  expect(within(region).getByText("新说法").closest(".diff-block")).toHaveClass("added");
  expect(within(region).queryByText("开头")).toBeNull();
});

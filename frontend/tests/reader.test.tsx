import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { SourcedContent } from "../src/components/content";

it("separates technical evidence, personal observation and unverified supplements without executing HTML", () => {
  const { container } = render(
    <SourcedContent
      sections={[
        { kind: "source_supported", text: "测试技术片段", citation_ids: ["tech/a?#"] },
        { kind: "personal_observation", text: "测试本人原话", citation_ids: ["note-1"] },
        {
          kind: "model_supplement",
          text: '测试补充 <script>alert(1)</script>\n\n![track](https://tracker.invalid/pixel.png)',
          citation_ids: [],
        },
      ]}
      citations={[
        {
          id: "tech/a?#", kind: "technical", title: "测试教程", excerpt: "测试摘录",
          source_url: null, revision: "r1",
        },
        {
          id: "note-1", kind: "journal", title: "测试原始记录", excerpt: "测试观察",
          source_url: null, revision: "r2",
        },
      ]}
    />,
  );
  expect(within(screen.getByRole("region", { name: "资料支持" })).getByText("测试技术片段"))
    .toBeVisible();
  expect(within(screen.getByRole("region", { name: "本人记录 · 主观观察" })).getByText("测试本人原话"))
    .toBeVisible();
  expect(screen.getByRole("region", { name: "模型补充 · 未经知识库核验" })).toBeVisible();
  expect(screen.getByRole("link", { name: /测试教程/ }))
    .toHaveAttribute("href", "#/evidence/tech%2Fa%3F%23");
  expect(container.querySelector("script, iframe, img")).toBeNull();
});

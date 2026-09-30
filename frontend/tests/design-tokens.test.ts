import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const app = join(__dirname, "../src/app");
const tokens = readFileSync(join(app, "tokens.css"), "utf8");
const globals = readFileSync(join(app, "globals.css"), "utf8");

function block(selector: string) {
  const open = tokens.indexOf("{", tokens.indexOf(selector));
  return tokens.slice(open + 1, tokens.indexOf("}", open));
}

function colors(css: string): Record<string, string> {
  return Object.fromEntries([...css.matchAll(/(--ot-[\w-]+):\s*(#[0-9a-f]{6})\b/gi)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

const light = colors(block(":root,"));
const dark = { ...light, ...colors(block('[data-theme="dark"]')) };
const texts = ["--ot-ink", "--ot-ink-2", "--ot-ink-3", "--ot-court", "--ot-gold-ink", "--ot-source",
  "--ot-journal", "--ot-model", "--ot-pending", "--ot-danger", "--ot-ok", "--ot-warn"];
const surfaces = ["--ot-paper", "--ot-surface", "--ot-rail"];
const fills = [["--ot-on-court", "--ot-court"], ["--ot-on-ok", "--ot-ok"],
  ["--ot-on-warn", "--ot-warn"], ["--ot-on-danger", "--ot-danger"]];

describe("design tokens", () => {
  it.each([["light", light], ["dark", dark]])("keeps %s text at 4.5:1 or better", (_, theme) => {
    for (const text of texts) {
      for (const surface of surfaces) {
        expect(contrast(theme[text], theme[surface]), `${text} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
    for (const [text, fill] of fills) {
      expect(contrast(theme[text], theme[fill]), `${text} on ${fill}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("styles components through tokens instead of raw colors", () => {
    expect(globals.match(/#[0-9a-f]{3,8}\b/gi) ?? []).toEqual([]);
  });

  it("never ships text smaller than 12px", () => {
    const sizes = [...globals.matchAll(/font(?:-size)?:[^;]*?(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
    expect(sizes.filter((size) => size < 12)).toEqual([]);
  });
});

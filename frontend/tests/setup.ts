import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Node 25+ ships its own global localStorage, which hides jsdom's working implementation.
const { jsdom } = globalThis as typeof globalThis & { jsdom?: { window: Window } };
if (jsdom && typeof globalThis.localStorage?.getItem !== "function") {
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: jsdom.window.localStorage });
}

afterEach(() => cleanup());

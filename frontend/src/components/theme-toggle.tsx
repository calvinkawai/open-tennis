"use client";

import { useEffect, useState } from "react";
import { THEME_KEY } from "../lib/theme";
import { Icon } from "./icons";

type Theme = "light" | "dark";

function storedTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => setTheme(storedTheme()), []);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return <button type="button" className="icon-button" aria-label={next === "dark" ? "切换到深色阅读" : "切换到浅色"}
    onClick={() => {
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        console.warn("theme_preference_not_saved");
      }
      setTheme(next);
    }}>
    <Icon name={next === "dark" ? "moon" : "sun"} />
  </button>;
}

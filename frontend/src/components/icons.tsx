const paths = {
  book: "M3 4.5h6c2 0 3 1 3 2 0-1 1-2 3-2h6v14h-6c-2 0-3 1-3 2 0-1-1-2-3-2H3ZM12 6.5v14",
  court: "M4 2.5h16v19H4ZM7 2.5v19M17 2.5v19M4 12h16M7 7h10M7 17h10M12 7v10",
  pen: "M4 20h4L19 9l-4-4L4 16ZM13.5 6.5l4 4M14 20h6",
  note: "M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM8 8h8M8 12h8M8 16h5",
  sun: "M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z",
  check: "m5 12.5 4.5 4.5L19 7.5",
  lock: "M7 11h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM8 11V8a4 4 0 0 1 8 0v3",
  clock: "M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0ZM12 7.5V12l3 2",
  alert: "M12 3.5 2.5 20h19ZM12 10v4.5M12 17.2v.3",
  offline: "M2.5 8.5a14 14 0 0 1 6-3M12 5a14 14 0 0 1 9.5 3.5M5.5 12a9.5 9.5 0 0 1 3.8-2.3M15.5 10.2A9.5 9.5 0 0 1 18.5 12M9 15.5a4.8 4.8 0 0 1 6 0M12 19h.01M3 3l18 18",
  online: "M2.5 8.5a14 14 0 0 1 19 0M5.5 12a9.5 9.5 0 0 1 13 0M9 15.5a4.8 4.8 0 0 1 6 0M12 19h.01",
  device: "M9 2.5h6a2 2 0 0 1 2 2v15a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-15a2 2 0 0 1 2-2ZM11 18h2",
  close: "M6.5 6.5l11 11M17.5 6.5l-11 11",
  chevron: "m9 5 7 7-7 7",
  external: "M7 17 17 7M8.5 7H17v8.5",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"
    focusable="false" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
    <path d={paths[name]} />
  </svg>;
}

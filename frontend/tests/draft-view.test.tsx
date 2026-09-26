import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { DraftView } from "../src/components/journal-views";
import { ApiClient } from "../src/lib/api";
import { newDraft, OfflineClient } from "../src/lib/offline";

it("does not discard an unsaved observation when connectivity changes", async () => {
  const api = new ApiClient(async () => Response.json([]));
  const offline = new OfflineClient(api, `editor-${crypto.randomUUID()}`);
  const draft = await offline.saveDraft(newDraft());
  const view = render(<DraftView id={draft.client_id} context={{ api, offline, online: true }} />);
  const input = await screen.findByLabelText("我的原话");
  await userEvent.type(input, "Keep this observation");

  view.rerender(<DraftView id={draft.client_id} context={{ api, offline, online: false }} />);

  expect(await screen.findByLabelText("我的原话")).toHaveValue("Keep this observation");
  expect(screen.getByRole("button", { name: "本人确认，提交到服务器" })).toBeDisabled();
});

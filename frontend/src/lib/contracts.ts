import { z } from "zod";

export const idSchema = z.string().min(1);
export const dateSchema = z.string().refine((value) => Number.isFinite(Date.parse(value)), {
  message: "Expected a valid timestamp",
});
export const spaceSchema = z.enum(["technical", "personal"]);
export type Space = z.infer<typeof spaceSchema>;

export const evidenceSchema = z.object({
  id: idSchema,
  kind: z.enum(["technical", "journal"]),
  title: z.string(),
  excerpt: z.string(),
  source_url: z.string().nullable(),
  revision: z.string(),
});
export const evidenceDetailSchema = evidenceSchema.extend({ content: z.string() });
export type Evidence = z.infer<typeof evidenceSchema>;
export type EvidenceDetail = z.infer<typeof evidenceDetailSchema>;

export const sectionSchema = z.object({
  kind: z.enum(["source_supported", "personal_observation", "model_supplement"]),
  text: z.string(),
  citation_ids: z.array(idSchema),
});
export type Section = z.infer<typeof sectionSchema>;

export const wikiSummarySchema = z.object({
  id: idSchema,
  space: spaceSchema,
  title: z.string(),
  topic: z.string(),
  version: z.number().int().nonnegative(),
  updated_at: dateSchema,
  has_draft: z.boolean(),
  index_status: z.enum(["pending", "ready", "failed"]),
  record_count: z.number().int().nonnegative(),
});
export type WikiSummary = z.infer<typeof wikiSummarySchema>;

export const wikiDetailSchema = wikiSummarySchema.extend({
  version_id: idSchema.nullable(),
  status: z.enum(["draft", "published", "empty"]),
  content: z.string(),
  sections: z.array(sectionSchema),
  citations: z.array(evidenceSchema),
  change_summary: z.string(),
});
export type WikiDetail = z.infer<typeof wikiDetailSchema>;

export const wikiVersionSchema = z.object({
  id: idSchema,
  page_id: idSchema,
  number: z.number().int().nonnegative(),
  status: z.enum(["draft", "published"]),
  content: z.string(),
  sections: z.array(sectionSchema),
  citations: z.array(evidenceSchema),
  created_at: dateSchema,
  change_summary: z.string(),
});
export type WikiVersion = z.infer<typeof wikiVersionSchema>;

export const runSchema = z.object({
  id: idSchema,
  kind: z.string(),
  status: z.enum(["queued", "running", "succeeded", "failed", "needs_input"]),
  page_id: idSchema.nullable(),
  entry_id: idSchema.nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: dateSchema,
  updated_at: dateSchema,
  result_version_id: idSchema.nullable(),
});
export type Run = z.infer<typeof runSchema>;

export const journalInputSchema = z.object({
  client_id: z.uuid(),
  plan_id: z.number().int().positive().nullable(),
  page_id: idSchema.nullable(),
  content: z.string(),
  context: z.string().nullable(),
  feeling: z.string().nullable(),
  completed_drill_ids: z.array(z.number().int().positive()),
});
export type JournalInput = z.infer<typeof journalInputSchema>;

export const journalSchema = journalInputSchema.extend({
  id: idSchema,
  created_at: dateSchema,
  run_id: idSchema.nullable(),
});
export type Journal = z.infer<typeof journalSchema>;

const drillContentSchema = z.object({
  name: z.string(),
  description: z.string(),
  video_url: z.string().nullable(),
});
export const planSchema = z.object({
  id: z.number().int().positive(),
  title: z.string(),
  focus_area: z.string(),
  raw_ai_content: z.string(),
  edited_content: z.string().nullable(),
  created_at: dateSchema,
  updated_at: dateSchema,
  drills: z.array(drillContentSchema.extend({
    id: z.number().int().positive(),
    training_plan_id: z.number().int().positive(),
  })),
  rendered_text: z.string(),
  sections: z.array(sectionSchema),
  citations: z.array(evidenceSchema),
  wiki_page_id: idSchema.nullable(),
});
export type Plan = z.infer<typeof planSchema>;

export const previewSchema = z.object({
  preview_id: idSchema,
  title: z.string(),
  focus_area: z.string(),
  raw_ai_content: z.string(),
  drills: z.array(drillContentSchema),
  sections: z.array(sectionSchema),
  citations: z.array(evidenceSchema),
  warning: z.string().nullable(),
  run_id: idSchema,
});
export type Preview = z.infer<typeof previewSchema>;

export const answerSchema = z.object({
  sections: z.array(sectionSchema),
  citations: z.array(evidenceSchema),
  run_id: idSchema,
  warning: z.string().nullable(),
});
export type Answer = z.infer<typeof answerSchema>;

export const statusSchema = z.object({
  agent_enabled: z.boolean(),
  model_configured: z.boolean(),
  sources_count: z.number().int().nonnegative(),
  pending_reviews: z.number().int().nonnegative(),
  ready: z.boolean(),
});
export type ServiceStatus = z.infer<typeof statusSchema>;

export type Question = { query: string; page_id: string | null; include_personal: boolean };
export type PlanEdit = {
  title?: string;
  edited_content?: string;
  drills?: { id: number; name?: string; description?: string }[];
};

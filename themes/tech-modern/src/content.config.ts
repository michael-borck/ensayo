import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

// Employees and documents arrive as files written by the Ensayo generator into
// src/data/. Committed fixtures in the same folders let the theme run
// standalone with `npm run dev`.

const employees = defineCollection({
  loader: glob({ pattern: "**/*.json", base: "./src/data/employees" }),
  schema: z.object({
    slug: z.string(),
    name: z.string(),
    role: z.string().default(""),
    title: z.string().nullable().optional(),
    tier: z.string().default("staff"),
    department: z.string().nullable().optional(),
    archetype: z.string().default("staff"),
    yearsAtCompany: z.number().nullable().optional(),
    yearsInIndustry: z.number().nullable().optional(),
    background: z.string().default(""),
    priorExperience: z.array(z.string()).default([]),
    personality: z.array(z.string()).default([]),
    knowledge: z.array(z.string()).default([]),
    opinions: z.array(z.string()).default([]),
    scenarioPerspective: z.string().default(""),
    refersTo: z.record(z.string()).default({}),
    chatbotMode: z.string().default("keyword"),
    chatbotEmbedId: z.string().nullable().optional(),
    anythingllm: z
      .object({ baseUrl: z.string().default(""), embedSrc: z.string().default("") })
      .optional(),
    keywords: z.any().optional(),
  }),
});

const docs = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/data/docs" }),
  schema: z.object({
    title: z.string(),
    type: z.string().default("custom"),
    brief: z.string().default(""),
  }),
});

export const collections = { employees, docs };

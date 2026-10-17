import { Hono } from "npm:hono";
import { cors } from "npm:hono/cors";
import { logger } from "npm:hono/logger";
import * as kv from "./kv_store.tsx";
const app = new Hono();
const prefix = "/make-server-d161f0b4";

// Enable logger
app.use('*', logger(console.log));

// Enable CORS for all routes and methods
app.use(
  "/*",
  cors({
    origin: "*",
    allowHeaders: ["Content-Type", "Authorization"],
    allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    exposeHeaders: ["Content-Length"],
    maxAge: 600,
  }),
);

// Health check endpoint
app.get(`${prefix}/health`, (c) => {
  return c.json({ status: "ok" });
});

const fallback = {
  contacts: [
    { id: "contact-lucy", name: "Lucy Chen", relationship: "Daughter", phone: "(415) 555-0182", email: "lucy@example.com", channel: "Text + call", primary: true },
    { id: "contact-patel", name: "Dr. Anika Patel", relationship: "Neurologist", phone: "(415) 555-0114", email: "anika.patel@example.com", channel: "Email", primary: false },
  ],
  alerts: [
    {
      id: "alert-rising",
      type: "increasing_tremor",
      severity: "urgent",
      title: "Increasing tremor pattern",
      reason: "Tremor intensity has risen for 18 minutes near Maria’s usual afternoon wearing-off window. The observed pattern may warrant a caregiver check-in.",
      createdAt: "2:42 PM",
      status: "open",
      routedTo: ["Lucy Chen", "Dr. Anika Patel"],
    },
    {
      id: "alert-missed",
      type: "missed_medication",
      severity: "attention",
      title: "Medication not yet recorded",
      reason: "The scheduled 12:00 PM Levodopa + Carbidopa dose has not been recorded 35 minutes after the reminder.",
      createdAt: "12:35 PM",
      status: "acknowledged",
      routedTo: ["Lucy Chen"],
      acknowledgedBy: "Lucy Chen",
    },
    {
      id: "alert-movement",
      type: "possible_dyskinesia",
      severity: "review",
      title: "Movement pattern needs review",
      reason: "Higher irregular movement was observed after two closely timed medication records. This may warrant clinician review for possible dyskinesia.",
      createdAt: "10:28 AM",
      status: "resolved",
      routedTo: ["Dr. Anika Patel"],
      acknowledgedBy: "Dr. Anika Patel",
    },
  ],
  schedule: {
    currentTime: "4:00 PM",
    suggestedTime: "3:30 PM",
    medication: "Levodopa + Carbidopa",
    dose: "100 / 25 mg",
    rationale: "On 8 observed days, tremor activity increased 30–45 minutes before the scheduled afternoon dose.",
    confidence: "Moderate",
    status: "review",
  },
};

async function getSafetyState() {
  const current = await kv.get("quell:safety");
  if (current) return current;
  await kv.set("quell:safety", fallback);
  return structuredClone(fallback);
}

app.get(`${prefix}/safety`, async (c) => {
  return c.json(await getSafetyState());
});

app.post(`${prefix}/contacts`, async (c) => {
  const contact = await c.req.json();
  if (!contact?.name || (!contact?.phone && !contact?.email)) {
    return c.json({ error: "Name and a phone number or email are required." }, 400);
  }
  const state = await getSafetyState();
  const saved = { ...contact, id: crypto.randomUUID() };
  state.contacts.push(saved);
  await kv.set("quell:safety", state);
  return c.json(saved, 201);
});

app.post(`${prefix}/alerts`, async (c) => {
  const { type } = await c.req.json();
  const state = await getSafetyState();
  const routedTo = state.contacts
    .filter((contact) => contact.primary || type !== "help_request")
    .map((contact) => contact.name);
  const templates = {
    increasing_tremor: {
      severity: "urgent",
      title: "Increasing tremor pattern",
      reason: "Tremor intensity has risen near Maria’s observed afternoon wearing-off window. The pattern may warrant a caregiver check-in.",
    },
    missed_medication: {
      severity: "attention",
      title: "Medication not yet recorded",
      reason: "A scheduled Levodopa + Carbidopa dose has not been recorded after the reminder window.",
    },
    possible_dyskinesia: {
      severity: "review",
      title: "Movement pattern needs review",
      reason: "Higher irregular movement was observed after closely timed medication records. This may warrant clinician review for possible dyskinesia.",
    },
    help_request: {
      severity: "urgent",
      title: "Maria requested immediate help",
      reason: "Maria used the long-press help control. Selected care contacts were notified with her latest device and medication context.",
    },
  };
  const template = templates[type];
  if (!template) return c.json({ error: "Unsupported alert type." }, 400);
  const alert = {
    id: crypto.randomUUID(),
    type,
    ...template,
    createdAt: "Just now",
    status: "open",
    routedTo,
  };
  state.alerts.unshift(alert);
  await kv.set("quell:safety", state);
  return c.json(alert, 201);
});

app.put(`${prefix}/alerts/:id`, async (c) => {
  const id = c.req.param("id");
  const { action } = await c.req.json();
  const state = await getSafetyState();
  const index = state.alerts.findIndex((alert) => alert.id === id);
  if (index < 0) return c.json({ error: "Alert not found." }, 404);
  const alert = state.alerts[index];
  alert.status = action === "acknowledge" ? "acknowledged" : "resolved";
  alert.acknowledgedBy = "Dr. Anika Patel";
  if (action === "medicine_administered") {
    alert.medicationAdministered = true;
  }
  state.alerts[index] = alert;
  await kv.set("quell:safety", state);
  return c.json(alert);
});

app.put(`${prefix}/schedule`, async (c) => {
  const { status } = await c.req.json();
  const state = await getSafetyState();
  state.schedule.status = status === "draft_shared" ? "draft_shared" : "review";
  await kv.set("quell:safety", state);
  return c.json(state.schedule);
});

Deno.serve(app.fetch);

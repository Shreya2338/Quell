import { projectId, publicAnonKey } from "../../utils/supabase/info";

export type EmergencyContact = {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  email: string;
  channel: "Text + call" | "Text" | "Email";
  primary: boolean;
};

export type CareAlertType =
  | "increasing_tremor"
  | "missed_medication"
  | "possible_dyskinesia"
  | "help_request";

export type CareAlert = {
  id: string;
  type: CareAlertType;
  severity: "urgent" | "attention" | "review";
  title: string;
  reason: string;
  createdAt: string;
  status: "open" | "acknowledged" | "resolved";
  routedTo: string[];
  acknowledgedBy?: string;
  medicationAdministered?: boolean;
};

export type SuggestedSchedule = {
  currentTime: string;
  suggestedTime: string;
  medication: string;
  dose: string;
  rationale: string;
  confidence: "Low" | "Moderate" | "High";
  status: "review" | "draft_shared";
};

export type SafetyState = {
  contacts: EmergencyContact[];
  alerts: CareAlert[];
  schedule: SuggestedSchedule;
};

export const fallbackSafetyState: SafetyState = {
  contacts: [
    {
      id: "contact-lucy",
      name: "Lucy Chen",
      relationship: "Daughter",
      phone: "(415) 555-0182",
      email: "lucy@example.com",
      channel: "Text + call",
      primary: true,
    },
    {
      id: "contact-patel",
      name: "Dr. Anika Patel",
      relationship: "Neurologist",
      phone: "(415) 555-0114",
      email: "anika.patel@example.com",
      channel: "Email",
      primary: false,
    },
  ],
  alerts: [
    {
      id: "alert-rising",
      type: "increasing_tremor",
      severity: "urgent",
      title: "Increasing tremor pattern",
      reason:
        "Tremor intensity has risen for 18 minutes near Maria’s usual afternoon wearing-off window. The observed pattern may warrant a caregiver check-in.",
      createdAt: "2:42 PM",
      status: "open",
      routedTo: ["Lucy Chen", "Dr. Anika Patel"],
    },
    {
      id: "alert-missed",
      type: "missed_medication",
      severity: "attention",
      title: "Medication not yet recorded",
      reason:
        "The scheduled 12:00 PM Levodopa + Carbidopa dose has not been recorded 35 minutes after the reminder.",
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
      reason:
        "Higher irregular movement was observed after two closely timed medication records. This may warrant clinician review for possible dyskinesia.",
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
    rationale:
      "On 8 observed days, tremor activity increased 30–45 minutes before the scheduled afternoon dose.",
    confidence: "Moderate",
    status: "review",
  },
};

const baseUrl = `https://${projectId}.supabase.co/functions/v1/server/make-server-d161f0b4`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${publicAnonKey}`,
      apikey: publicAnonKey,
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Care service returned ${response.status}`);
  }

  return response.json();
}

export const safetyApi = {
  getState: () => request<SafetyState>("/safety"),
  addContact: (contact: Omit<EmergencyContact, "id">) =>
    request<EmergencyContact>("/contacts", {
      method: "POST",
      body: JSON.stringify(contact),
    }),
  createAlert: (type: CareAlertType) =>
    request<CareAlert>("/alerts", {
      method: "POST",
      body: JSON.stringify({ type }),
    }),
  updateAlert: (
    id: string,
    action: "acknowledge" | "medicine_administered" | "resolve",
  ) =>
    request<CareAlert>(`/alerts/${id}`, {
      method: "PUT",
      body: JSON.stringify({ action }),
    }),
  shareSchedule: () =>
    request<SuggestedSchedule>("/schedule", {
      method: "PUT",
      body: JSON.stringify({ status: "draft_shared" }),
    }),
};

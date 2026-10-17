import { useEffect, useRef, useState } from "react";
import {
  CareAlert,
  CareAlertType,
  EmergencyContact,
  fallbackSafetyState,
  safetyApi,
  SafetyState,
} from "./lib/safetyApi";

type Props = {
  role: "patient" | "clinician";
  toast: (message: string) => void;
  notify: (message: string) => void;
};

const alertLabels: Record<CareAlertType, string> = {
  increasing_tremor: "Increasing tremor",
  missed_medication: "Missed medication",
  possible_dyskinesia: "Movement review",
  help_request: "Immediate help request",
};

function AlertCard({
  alert,
  clinician,
  onAction,
}: {
  alert: CareAlert;
  clinician: boolean;
  onAction: (
    id: string,
    action: "acknowledge" | "medicine_administered" | "resolve",
  ) => void;
}) {
  return (
    <article className={`care-alert ${alert.severity} ${alert.status}`}>
      <div className="care-alert-top">
        <span className="alert-type">{alertLabels[alert.type]}</span>
        <span className={`alert-status ${alert.status}`}>
          {alert.status === "open"
            ? "Action needed"
            : alert.status === "acknowledged"
              ? "Acknowledged"
              : "Resolved"}
        </span>
      </div>
      <h3>{alert.title}</h3>
      <p>{alert.reason}</p>
      <div className="alert-routing">
        <span>{alert.createdAt}</span>
        <span>Routed to {alert.routedTo.join(" and ")}</span>
      </div>
      {alert.acknowledgedBy && (
        <div className="alert-confirmation">
          Acknowledged by {alert.acknowledgedBy}
          {alert.medicationAdministered ? " · Medication recorded" : ""}
        </div>
      )}
      {clinician && alert.status !== "resolved" && (
        <div className="alert-actions">
          {alert.status === "open" && (
            <button
              className="btn secondary"
              onClick={() => onAction(alert.id, "acknowledge")}
            >
              <span>Acknowledge</span>
            </button>
          )}
          {alert.type === "missed_medication" &&
            !alert.medicationAdministered && (
              <button
                className="btn primary"
                onClick={() =>
                  onAction(alert.id, "medicine_administered")
                }
              >
                <span>Medicine administered</span>
              </button>
            )}
          <button
            className="text-link"
            onClick={() => onAction(alert.id, "resolve")}
          >
            Resolve
          </button>
        </div>
      )}
    </article>
  );
}

export default function CareSafety({ role, toast, notify }: Props) {
  const [state, setState] = useState<SafetyState>(fallbackSafetyState);
  const [loading, setLoading] = useState(true);
  const [showContactForm, setShowContactForm] = useState(false);
  const [holding, setHolding] = useState(false);
  const [helpSent, setHelpSent] = useState(false);
  const [contact, setContact] = useState({
    name: "",
    relationship: "",
    phone: "",
    email: "",
    channel: "Text + call" as EmergencyContact["channel"],
    primary: false,
  });
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    safetyApi
      .getState()
      .then(setState)
      .catch(() => {
        toast("Using prototype care data while the alert service reconnects");
      })
      .finally(() => setLoading(false));
  }, []);

  const addContact = async () => {
    if (!contact.name || (!contact.phone && !contact.email)) return;
    const localContact = { ...contact, id: `contact-${Date.now()}` };
    setState((current) => ({
      ...current,
      contacts: [...current.contacts, localContact],
    }));
    setContact({
      name: "",
      relationship: "",
      phone: "",
      email: "",
      channel: "Text + call",
      primary: false,
    });
    setShowContactForm(false);
    toast("Emergency contact added");
    try {
      const saved = await safetyApi.addContact(contact);
      setState((current) => ({
        ...current,
        contacts: current.contacts.map((item) =>
          item.id === localContact.id ? saved : item,
        ),
      }));
    } catch {
      toast("Contact saved in this prototype session");
    }
  };

  const createAlert = async (type: CareAlertType) => {
    const templates = {
      increasing_tremor: fallbackSafetyState.alerts[0],
      missed_medication: fallbackSafetyState.alerts[1],
      possible_dyskinesia: fallbackSafetyState.alerts[2],
      help_request: {
        id: `alert-help-${Date.now()}`,
        type: "help_request" as const,
        severity: "urgent" as const,
        title: "Maria requested immediate help",
        reason:
          "Maria used the long-press help control. Her selected care contacts were notified with her latest device and medication context.",
        createdAt: "Just now",
        status: "open" as const,
        routedTo: state.contacts
          .filter((item) => item.primary)
          .map((item) => item.name),
      },
    };
    const localAlert = {
      ...templates[type],
      id: `alert-${Date.now()}`,
      createdAt: "Just now",
      status: "open" as const,
    };
    setState((current) => ({
      ...current,
      alerts: [localAlert, ...current.alerts],
    }));
    notify(`${localAlert.title}: ${localAlert.reason}`);
    try {
      const saved = await safetyApi.createAlert(type);
      setState((current) => ({
        ...current,
        alerts: current.alerts.map((item) =>
          item.id === localAlert.id ? saved : item,
        ),
      }));
    } catch {
      toast("Alert created in this prototype session");
    }
  };

  const updateAlert = async (
    id: string,
    action: "acknowledge" | "medicine_administered" | "resolve",
  ) => {
    setState((current) => ({
      ...current,
      alerts: current.alerts.map((alert) =>
        alert.id === id
          ? {
              ...alert,
              status:
                action === "resolve" || action === "medicine_administered"
                  ? "resolved"
                  : "acknowledged",
              acknowledgedBy: "Dr. Anika Patel",
              medicationAdministered:
                action === "medicine_administered"
                  ? true
                  : alert.medicationAdministered,
            }
          : alert,
      ),
    }));
    toast(
      action === "medicine_administered"
        ? "Medication aid recorded and care contacts updated"
        : action === "resolve"
          ? "Alert resolved"
          : "Alert acknowledged",
    );
    try {
      const saved = await safetyApi.updateAlert(id, action);
      setState((current) => ({
        ...current,
        alerts: current.alerts.map((item) => (item.id === id ? saved : item)),
      }));
    } catch {
      // The optimistic prototype state remains usable if the function is offline.
    }
  };

  const startHelpHold = () => {
    if (helpSent || holdTimer.current) return;
    setHolding(true);
    holdTimer.current = setTimeout(async () => {
      holdTimer.current = null;
      setHolding(false);
      setHelpSent(true);
      await createAlert("help_request");
      toast("Help request sent to your primary contact");
    }, 1400);
  };

  const cancelHelpHold = () => {
    if (holdTimer.current) clearTimeout(holdTimer.current);
    holdTimer.current = null;
    setHolding(false);
  };

  const shareSchedule = async () => {
    setState((current) => ({
      ...current,
      schedule: { ...current.schedule, status: "draft_shared" },
    }));
    notify(
      "Dr. Patel shared a medication timing draft for review. No medication changes have been applied.",
    );
    toast("Schedule draft shared with Maria");
    try {
      const schedule = await safetyApi.shareSchedule();
      setState((current) => ({ ...current, schedule }));
    } catch {
      // Keep the local prototype state.
    }
  };

  const clinician = role === "clinician";
  const openAlerts = state.alerts.filter((alert) => alert.status !== "resolved");

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{clinician ? "Care alerts" : "Help & care network"}</h1>
          <p>
            {clinician
              ? "Review observed patterns, contact routing, and medication timing drafts."
              : "Choose who should be contacted and request help when you need it."}
          </p>
        </div>
        {loading && <span className="care-sync">Syncing care data…</span>}
      </div>

      {!clinician && (
        <section className="help-panel">
          <div>
            <span className="eyebrow">IMMEDIATE SUPPORT</span>
            <h2>Need someone to check in?</h2>
            <p>
              Press and hold to notify your primary care contact with the reason,
              latest wristband status, and medication context.
            </p>
          </div>
          <button
            className={`hold-help ${holding ? "holding" : ""} ${helpSent ? "sent" : ""}`}
            onPointerDown={startHelpHold}
            onPointerUp={cancelHelpHold}
            onPointerLeave={cancelHelpHold}
            onPointerCancel={cancelHelpHold}
            disabled={helpSent}
          >
            <span>
              {helpSent
                ? "Help request sent"
                : holding
                  ? "Keep holding…"
                  : "Press and hold for help"}
            </span>
            <small>
              {helpSent ? "Lucy Chen was notified" : "Hold for 1.4 seconds"}
            </small>
          </button>
        </section>
      )}

      <div className="care-layout">
        <section className="card care-alerts-card">
          <div className="card-head">
            <div>
              <h2>{clinician ? "Active care queue" : "Recent care alerts"}</h2>
              <p>
                {clinician
                  ? `${openAlerts.length} alerts need review`
                  : "What your care network has received"}
              </p>
            </div>
            <span className="badge warning">{openAlerts.length} active</span>
          </div>
          <div className="care-alert-list">
            {state.alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                clinician={clinician}
                onAction={updateAlert}
              />
            ))}
          </div>
        </section>

        <div className="care-side">
          {clinician && (
            <section className="card schedule-suggestion">
              <span className="eyebrow">MEDICATION TIMING REVIEW</span>
              <div className="schedule-shift">
                <span>
                  <small>Current</small>
                  <strong>{state.schedule.currentTime}</strong>
                </span>
                <b>→</b>
                <span>
                  <small>Suggested review time</small>
                  <strong>{state.schedule.suggestedTime}</strong>
                </span>
              </div>
              <h2>{state.schedule.medication}</h2>
              <p>{state.schedule.rationale}</p>
              <dl>
                <div>
                  <dt>Dose</dt>
                  <dd>{state.schedule.dose}</dd>
                </div>
                <div>
                  <dt>Pattern confidence</dt>
                  <dd>{state.schedule.confidence}</dd>
                </div>
              </dl>
              <div className="schedule-caution">
                Decision support only. This draft does not change a prescription
                or medication schedule.
              </div>
              <button
                className="btn primary"
                onClick={shareSchedule}
                disabled={state.schedule.status === "draft_shared"}
              >
                <span>
                  {state.schedule.status === "draft_shared"
                    ? "Draft shared"
                    : "Share draft for review"}
                </span>
              </button>
            </section>
          )}

          <section className="card contact-card">
            <div className="card-head">
              <div>
                <h2>Emergency contacts</h2>
                <p>Alert routing for Maria Chen</p>
              </div>
              {!clinician && (
                <button
                  className="text-link"
                  onClick={() => setShowContactForm(!showContactForm)}
                >
                  {showContactForm ? "Cancel" : "Add contact"}
                </button>
              )}
            </div>

            {showContactForm && (
              <div className="contact-form">
                <label>
                  <span>Name</span>
                  <input
                    value={contact.name}
                    onChange={(event) =>
                      setContact({ ...contact, name: event.target.value })
                    }
                    placeholder="Full name"
                  />
                </label>
                <label>
                  <span>Relationship</span>
                  <input
                    value={contact.relationship}
                    onChange={(event) =>
                      setContact({
                        ...contact,
                        relationship: event.target.value,
                      })
                    }
                    placeholder="Family, caregiver, clinician"
                  />
                </label>
                <label>
                  <span>Phone</span>
                  <input
                    value={contact.phone}
                    onChange={(event) =>
                      setContact({ ...contact, phone: event.target.value })
                    }
                    placeholder="Phone number"
                  />
                </label>
                <label>
                  <span>Email</span>
                  <input
                    value={contact.email}
                    onChange={(event) =>
                      setContact({ ...contact, email: event.target.value })
                    }
                    placeholder="Email address"
                  />
                </label>
                <label>
                  <span>Alert method</span>
                  <select
                    value={contact.channel}
                    onChange={(event) =>
                      setContact({
                        ...contact,
                        channel: event.target
                          .value as EmergencyContact["channel"],
                      })
                    }
                  >
                    <option>Text + call</option>
                    <option>Text</option>
                    <option>Email</option>
                  </select>
                </label>
                <label className="primary-check">
                  <input
                    type="checkbox"
                    checked={contact.primary}
                    onChange={(event) =>
                      setContact({
                        ...contact,
                        primary: event.target.checked,
                      })
                    }
                  />
                  <span>Use as primary help contact</span>
                </label>
                <button
                  className="btn primary"
                  onClick={addContact}
                  disabled={
                    !contact.name || (!contact.phone && !contact.email)
                  }
                >
                  <span>Save contact</span>
                </button>
              </div>
            )}

            <div className="contact-list">
              {state.contacts.map((item) => (
                <article key={item.id}>
                  <span className="contact-initials">
                    {item.name
                      .split(" ")
                      .map((part) => part[0])
                      .join("")}
                  </span>
                  <div>
                    <strong>{item.name}</strong>
                    <small>
                      {item.relationship} · {item.channel}
                    </small>
                    <span>{item.phone || item.email}</span>
                  </div>
                  {item.primary && <span className="badge purple">Primary</span>}
                </article>
              ))}
            </div>
          </section>

          {clinician && (
            <section className="card scenario-card">
              <h2>Prototype alert scenarios</h2>
              <p>
                Trigger a fictional care event to demonstrate routing and
                acknowledgement.
              </p>
              <button onClick={() => createAlert("increasing_tremor")}>
                Increasing tremor pattern
              </button>
              <button onClick={() => createAlert("missed_medication")}>
                Medication missed
              </button>
              <button onClick={() => createAlert("possible_dyskinesia")}>
                Possible dyskinesia review
              </button>
              <small>
                External SMS, calls, PointClickCare, and email delivery require a
                configured integration provider.
              </small>
            </section>
          )}
        </div>
      </div>
    </>
  );
}

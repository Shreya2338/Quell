import { useMemo, useRef, useState } from "react";

/**
 * TremorHeatmap
 * Intensity (MDS-UPDRS-style 0–4) by hour of day (x) and day of week (y).
 *
 * Props (all optional – demo data is generated if omitted):
 *   samples: [{ day: 0-6 (Mon=0), hour: 0-24 (decimal), intensity: 0-4 }]
 *   doses:   [{ day: 0-6, hour: 0-24 (decimal), label: "Levodopa 100 mg" }]
 */

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOUR_STEPS = [1, 2, 3, 4, 6, 8, 12];
const DAY_MODES = [
  { label: "Each day", groups: [[0], [1], [2], [3], [4], [5], [6]] },
  { label: "Weekdays / weekend", groups: [[0, 1, 2, 3, 4], [5, 6]], names: ["Mon–Fri", "Sat–Sun"] },
  { label: "Whole week", groups: [[0, 1, 2, 3, 4, 5, 6]], names: ["Mon–Sun"] },
];

const SCALE = [
  [0, [251, 247, 236]],
  [1, [227, 218, 239]],
  [2, [179, 163, 209]],
  [3, [122, 101, 159]],
  [4, [63, 52, 96]],
];
const CLASSES = ["None", "Slight", "Mild", "Moderate", "Severe"];

const C = {
  bg: "#FFFDF9",
  ink: "#17150F",
  muted: "#6E6A64",
  purple: "#4F4470",
  orange: "#F2A65A",
  orangeDeep: "#E28B33",
  peach: "#FCE8B8",
  brown: "#7A4E22",
  grid: "#EDE6D3",
};

/* ---------- helpers ---------- */

function colorFor(v) {
  const x = Math.max(0, Math.min(4, v));
  for (let i = 0; i < SCALE.length - 1; i++) {
    const [a, ca] = SCALE[i];
    const [b, cb] = SCALE[i + 1];
    if (x <= b) {
      const t = (x - a) / (b - a);
      return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * t)).join(",")})`;
    }
  }
  return "rgb(63,52,96)";
}
const textOn = (v) => (v > 2.4 ? "#FFFDF9" : C.ink);

function fmtTime(h) {
  const total = Math.round(h * 60) % (24 * 60);
  const hh = Math.floor(total / 60);
  const mm = total % 60;
  const ap = hh >= 12 ? "PM" : "AM";
  const h12 = hh % 12 === 0 ? 12 : hh % 12;
  return mm ? `${h12}:${String(mm).padStart(2, "0")} ${ap}` : `${h12} ${ap}`;
}
const classify = (v) => CLASSES[Math.min(4, Math.round(v))];

/* ---------- demo data (seeded so it doesn't jump around) ---------- */

function makeDemo() {
  let s = 7;
  const rand = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const doseTimes = [8.5, 13.75, 18.5];
  const doses = [];
  const samples = [];
  for (let d = 0; d < 7; d++) {
    const times = doseTimes.map((t) => t + (rand() - 0.5) * 0.6);
    times.forEach((t) => doses.push({ day: d, hour: t, label: "Levodopa 100 mg" }));
    for (let h = 0; h < 24; h += 0.25) {
      const prior = times.filter((t) => t <= h);
      const since = prior.length ? h - prior[prior.length - 1] : 12;
      // relief after a dose, wearing off from ~3–5 h
      const wear = Math.min(1, Math.max(0, (since - 1) / 4));
      let v = 0.5 + 2.3 * wear * wear * (3 - 2 * wear) * 0.9;
      if (since < 1) v = 0.9 + since * 0.3;
      if (h < 6.5 || h > 22.5) v *= 0.15; // sleep
      v += (rand() - 0.5) * 0.5 + (d >= 5 ? 0.2 : 0);
      samples.push({ day: d, hour: h, intensity: Math.max(0, Math.min(4, v)) });
    }
  }
  return { samples, doses };
}

/* ---------- component ---------- */

export default function TremorHeatmap({ samples, doses, defaultHourStep = 4 }) {
  const demo = useMemo(makeDemo, []);
  const data = samples ?? demo.samples;
  const meds = doses ?? demo.doses;

  const [hourIdx, setHourIdx] = useState(Math.max(0, HOUR_STEPS.indexOf(defaultHourStep)));
  const [dayIdx, setDayIdx] = useState(0);
  const [showDoses, setShowDoses] = useState(true);
  const [tip, setTip] = useState(null);
  const wrapRef = useRef(null);

  const step = HOUR_STEPS[hourIdx];
  const bins = 24 / step;
  const mode = DAY_MODES[dayIdx];

  const rows = useMemo(() => {
    return mode.groups.map((group, gi) => {
      const cells = Array.from({ length: bins }, (_, b) => {
        const from = b * step;
        const to = from + step;
        const inside = data.filter(
          (p) => group.includes(p.day) && p.hour >= from && p.hour < to
        );
        const mean = inside.length
          ? inside.reduce((a, p) => a + p.intensity, 0) / inside.length
          : null;
        const peak = inside.length ? Math.max(...inside.map((p) => p.intensity)) : null;
        const cellDoses = meds.filter(
          (m) => group.includes(m.day) && m.hour >= from && m.hour < to
        );
        return { from, to, mean, peak, n: inside.length, cellDoses };
      });
      const groupDoses = meds.filter((m) => group.includes(m.day));
      return {
        name: mode.names ? mode.names[gi] : DAYS[group[0]],
        group,
        cells,
        doses: groupDoses,
      };
    });
  }, [data, meds, bins, step, mode]);

  function placeTip(e, content) {
    const box = wrapRef.current.getBoundingClientRect();
    let x, y;
    if (e.clientX || e.clientY) {
      x = e.clientX - box.left;
      y = e.clientY - box.top;
    } else {
      const r = e.currentTarget.getBoundingClientRect();
      x = r.left - box.left + r.width / 2;
      y = r.top - box.top;
    }
    setTip({ x, y, content });
  }

  const cellTip = (row, c) => {
    const single = row.group.length === 1;
    let since = null;
    if (single) {
      const before = meds
        .filter((m) => m.day === row.group[0] && m.hour <= c.from)
        .sort((a, b) => b.hour - a.hour)[0];
      if (before) since = c.from - before.hour;
    }
    return { type: "cell", row, c, since };
  };

  const hourLabelEvery = bins > 12 ? 2 : 1;

  return (
    <div
      ref={wrapRef}
      className="tremor-heatmap"
      style={{
        position: "relative",
        background: "transparent",
        color: C.ink,
        fontFamily: "'DM Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
        marginTop: 24,
      }}
      onMouseLeave={() => setTip(null)}
    >
      <style>{`
        .th-range{-webkit-appearance:none;appearance:none;width:100%;height:4px;border-radius:4px;background:${C.grid};outline:none;margin:10px 0 6px}
        .th-range::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:${C.purple};border:3px solid ${C.bg};box-shadow:0 0 0 1px ${C.purple};cursor:pointer}
        .th-range::-moz-range-thumb{width:14px;height:14px;border-radius:50%;background:${C.purple};border:3px solid ${C.bg};box-shadow:0 0 0 1px ${C.purple};cursor:pointer}
        .th-range:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 3px ${C.orange}}
        .th-cell{transition:transform .12s ease, box-shadow .12s ease;outline:none}
        .th-cell:hover,.th-cell:focus-visible{transform:scale(1.06);box-shadow:0 0 0 2px ${C.purple};z-index:3}
        .th-dot{transition:transform .12s ease}
        .th-dot:hover,.th-dot:focus-visible{transform:translate(-50%,-50%) scale(1.35)!important;outline:none}
        .th-switch:focus-visible{box-shadow:0 0 0 3px ${C.orange}}
        @media (prefers-reduced-motion:reduce){.th-cell,.th-dot{transition:none}}
      `}</style>

      {/* heatmap */}
      <div style={{ display: "flex", gap: 10 }}>
        {/* day labels */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4, width: mode.names ? 64 : 40, flexShrink: 0 }}>
          {rows.map((r) => (
            <div
              key={r.name}
              style={{
                height: rows.length === 1 ? 52 : rows.length === 2 ? 44 : 28,
                display: "flex",
                alignItems: "center",
                fontSize: 10,
                color: C.muted,
              }}
            >
              {r.name}
            </div>
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {rows.map((row) => {
              const h = rows.length === 1 ? 52 : rows.length === 2 ? 44 : 28;
              return (
                <div key={row.name} style={{ position: "relative", height: h }}>
                  <div style={{ display: "flex", gap: 2, height: "100%" }}>
                    {row.cells.map((c, i) => {
                      const has = c.mean !== null;
                      return (
                        <div
                          key={i}
                          className="th-cell"
                          tabIndex={0}
                          role="img"
                          aria-label={`${row.name}, ${fmtTime(c.from)} to ${fmtTime(c.to)}: ${
                            has ? `${c.mean.toFixed(1)} of 4, ${classify(c.mean)}` : "no data"
                          }`}
                          onMouseMove={(e) => placeTip(e, cellTip(row, c))}
                          onFocus={(e) => placeTip(e, cellTip(row, c))}
                          onBlur={() => setTip(null)}
                          style={{
                            flex: 1,
                            borderRadius: bins > 12 ? 4 : 6,
                            background: has ? colorFor(c.mean) : "transparent",
                            border: has ? "none" : `1px dashed ${C.grid}`,
                            position: "relative",
                            cursor: "crosshair",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 10,
                            fontWeight: 600,
                            color: has ? textOn(c.mean) : C.muted,
                          }}
                        >
                          {has && bins <= 8 ? c.mean.toFixed(1) : ""}
                        </div>
                      );
                    })}
                  </div>

                  {/* medication markers */}
                  {showDoses && (
                    <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
                      {row.doses.map((m, i) => (
                        <span
                          key={i}
                          className="th-dot"
                          tabIndex={0}
                          role="img"
                          aria-label={`${m.label} at ${fmtTime(m.hour)}`}
                          onMouseMove={(e) => {
                            e.stopPropagation();
                            placeTip(e, { type: "dose", m });
                          }}
                          onFocus={(e) => placeTip(e, { type: "dose", m })}
                          onBlur={() => setTip(null)}
                          style={{
                            position: "absolute",
                            left: `${(m.hour / 24) * 100}%`,
                            top: row.group.length > 1 ? `${15 + ((i * 17) % 70)}%` : "50%",
                            width: 12,
                            height: 12,
                            borderRadius: "50%",
                            background: C.orange,
                            border: `2px solid ${C.bg}`,
                            boxShadow: `0 0 0 1px ${C.orangeDeep}`,
                            transform: "translate(-50%,-50%)",
                            pointerEvents: "auto",
                            cursor: "pointer",
                            zIndex: 4,
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* hour axis */}
          <div style={{ display: "flex", gap: 2, marginTop: 8 }}>
            {Array.from({ length: bins }, (_, i) => (
              <div key={i} style={{ flex: 1, fontSize: 9, color: C.muted, minWidth: 0 }}>
                {i % hourLabelEvery === 0 ? fmtTime(i * step) : ""}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* legend */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14, marginTop: 14, fontSize: 10, color: C.muted }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>None</span>
          <div
            style={{
              width: 90,
              height: 8,
              borderRadius: 6,
              background: `linear-gradient(90deg, ${[0, 1, 2, 3, 4].map(colorFor).join(",")})`,
            }}
          />
          <span>Severe</span>
        </div>
        {showDoses && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{ width: 12, height: 12, borderRadius: "50%", background: C.orange, boxShadow: `0 0 0 1px ${C.orangeDeep}` }}
            />
            Medication taken
          </div>
        )}
      </div>

      {/* tooltip */}
      {tip && (
        <div
          role="tooltip"
          style={{
            position: "absolute",
            left: Math.min(tip.x + 16, (wrapRef.current?.clientWidth ?? 600) - 250),
            top: Math.max(8, tip.y - 12),
            transform: tip.y > 140 ? "translateY(-100%)" : "none",
            width: 232,
            background: C.ink,
            color: C.bg,
            borderRadius: 14,
            padding: "12px 14px",
            fontSize: 13,
            lineHeight: 1.5,
            pointerEvents: "none",
            zIndex: 20,
            boxShadow: "0 8px 24px rgba(23,21,15,.25)",
          }}
        >
          {tip.content.type === "dose" ? (
            <>
              <div style={{ fontWeight: 700, color: C.orange }}>{tip.content.m.label}</div>
              <div>Taken at {fmtTime(tip.content.m.hour)}</div>
              <div style={{ opacity: 0.65 }}>{DAYS[tip.content.m.day]}</div>
            </>
          ) : (
            <CellTip {...tip.content} />
          )}
        </div>
      )}
    </div>
  );
}

function CellTip({ row, c, since }) {
  const has = c.mean !== null;
  return (
    <>
      <div style={{ fontWeight: 700 }}>
        {row.name}, {fmtTime(c.from)}–{fmtTime(c.to)}
      </div>
      {has ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 0" }}>
            <span style={{ width: 14, height: 14, borderRadius: 4, background: colorFor(c.mean), border: "1px solid rgba(255,255,255,.3)" }} />
            <span>
              <strong>{c.mean.toFixed(1)}</strong> / 4 · {classify(c.mean)}
            </span>
          </div>
          <div style={{ opacity: 0.7 }}>Peak {c.peak.toFixed(1)} · {c.n} readings</div>
          {since !== null && (
            <div style={{ opacity: 0.7 }}>{since.toFixed(1)} h since last dose</div>
          )}
          {c.cellDoses.length > 0 && (
            <div style={{ color: C.orange, marginTop: 4 }}>
              Dose: {c.cellDoses.map((d) => fmtTime(d.hour)).join(", ")}
            </div>
          )}
        </>
      ) : (
        <div style={{ opacity: 0.7 }}>No readings in this window.</div>
      )}
    </>
  );
}

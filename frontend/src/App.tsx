import { FormEvent, ReactNode, useMemo, useState } from "react";
import CareSafety from "./CareSafety";
import TremorHeatmap from "./TremorHeatmap";
import WristbandViewer from "./WristbandViewer";

type Role = "patient" | "clinician";
type Route =
  | "landing" | "login" | "signup" | "forgot" | "reset" | "verify" | "setup"
  | "dashboard" | "medication" | "tremors" | "symptoms" | "timeline" | "therapy" | "device" | "profile"
  | "patients" | "patient" | "analytics" | "reports" | "notes" | "settings" | "safety";

type Medication = { id: number; name: string; dose: string; time: string; actual?: string; status: "Taken" | "Upcoming"; latency?: string };
type Note = { id: number; text: string; date: string; pinned: boolean };

const C = {
  purple: "#59466D", orange: "#FFAE67", peach: "#FFE8B5", cream: "#FFFBE4",
  lavender: "#DCCFE8", pale: "#EEE8F2", success: "#6FAF82", danger: "#D96C6C",
};

const Icon = ({ name, size = 20 }: { name: string; size?: number }) => {
  const paths: Record<string, ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    pill: <><path d="M10.5 5.5 5.5 10.5a4.2 4.2 0 0 0 6 6l5-5a4.2 4.2 0 0 0-6-6Z"/><path d="m8 8 8 8"/></>,
    wave: <path d="M2 12h4l2.2-7 3.3 14 2.8-10 2.2 6H22"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    spark: <><path d="M12 2 9.8 9.8 2 12l7.8 2.2L12 22l2.2-7.8L22 12l-7.8-2.2Z"/></>,
    watch: <><rect x="7" y="6" width="10" height="12" rx="3"/><path d="m9 6 1-4h4l1 4M9 18l1 4h4l1-4"/><path d="M10 12h1l1-2 1 4 1-2h1"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M17 11a4 4 0 0 0 0-8M22 21v-2a4 4 0 0 0-3-3.9"/></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
    file: <><path d="M6 2h8l4 4v16H6Z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>,
    note: <><path d="M4 3h16v18H4Z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    search: <><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    arrow: <path d="m9 18 6-6-6-6"/>,
    close: <path d="m6 6 12 12M18 6 6 18"/>,
    menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 3h7v18h-7"/></>,
    download: <><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 19h16"/></>,
    print: <><path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6Z"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.spark}</svg>;
};

function Button({ children, onClick, variant = "primary", icon, type = "button", disabled = false }: { children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost" | "danger"; icon?: string; type?: "button" | "submit"; disabled?: boolean }) {
  return <button className={`btn ${variant}`} onClick={onClick} type={type} disabled={disabled}>{icon && <Icon name={icon} size={18}/>}<span>{children}</span></button>;
}
function Field({ label, type = "text", placeholder, value, onChange }: { label: string; type?: string; placeholder?: string; value?: string; onChange?: (v: string) => void }) {
  return <label className="field"><span>{label}</span><input type={type} placeholder={placeholder} value={value} onChange={(e) => onChange?.(e.target.value)}/></label>;
}
function Card({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{children}</section>; }
function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span>; }
function Toggle({ value, onChange, label }: { value: boolean; onChange: () => void; label: string }) {
  return <button className={`toggle-row ${value ? "on" : ""}`} onClick={onChange} aria-pressed={value}><span>{label}</span><span className="switch"><i/></span></button>;
}
function Tabs({ items, value, onChange }: { items: string[]; value: string; onChange: (v: string) => void }) {
  return <div className="tabs">{items.map((item) => <button key={item} className={value === item ? "active" : ""} onClick={() => onChange(item)}>{item}</button>)}</div>;
}

const seedMeds: Medication[] = [
  { id: 1, name: "Levodopa + Carbidopa", dose: "100 / 25 mg", time: "8:00 AM", actual: "8:02 AM", status: "Taken", latency: "36 min" },
  { id: 2, name: "Levodopa + Carbidopa", dose: "100 / 25 mg", time: "12:00 PM", actual: "12:04 PM", status: "Taken", latency: "38 min" },
  { id: 3, name: "Levodopa + Carbidopa", dose: "100 / 25 mg", time: "4:00 PM", status: "Upcoming" },
  { id: 4, name: "Levodopa + Carbidopa", dose: "100 / 25 mg", time: "8:00 PM", status: "Upcoming" },
];
const episodes = [
  { time: "10:14 AM", duration: "42 sec", frequency: "4.6 Hz", intensity: 42, response: "−21%", start: "10:14 AM", end: "10:14:42 AM" },
  { time: "1:38 PM", duration: "1m 21s", frequency: "4.8 Hz", intensity: 68, response: "−32%", start: "1:38 PM", end: "1:39:21 PM" },
  { time: "5:02 PM", duration: "2m 10s", frequency: "5.0 Hz", intensity: 74, response: "−18%", start: "5:02 PM", end: "5:04:10 PM" },
];
const patients = [
  { name: "Maria Chen", age: 67, status: "Needs review", sync: "2 min ago", trend: "↑ 14%", adherence: "94%", review: "Sept 30" },
  { name: "James Wilson", age: 71, status: "Stable", sync: "8 min ago", trend: "↓ 8%", adherence: "97%", review: "Oct 2" },
  { name: "Elena Ruiz", age: 63, status: "Recent episode", sync: "24 min ago", trend: "↑ 5%", adherence: "89%", review: "Sept 28" },
  { name: "Robert Kim", age: 75, status: "Stable", sync: "1 hr ago", trend: "↓ 11%", adherence: "96%", review: "Oct 1" },
  { name: "Amina Okafor", age: 69, status: "Needs review", sync: "3 hrs ago", trend: "↑ 18%", adherence: "84%", review: "Sept 26" },
];

function Logo({ light = false }: { light?: boolean }) {
  return <div className={`logo ${light ? "light" : ""}`}><span className="logo-mark"><Icon name="wave" size={22}/></span><strong>QUELL</strong></div>;
}

function LineChart({ range = "7 days", medication = false, area = true }: { range?: string; medication?: boolean; area?: boolean }) {
  const multiplier = range === "30 days" || range === "90 days" ? 1.1 : range === "Today" ? .72 : 1;
  const pts = [62,54,32,27,30,49,68,58,35,29,31,55,74,50,33].map((v) => Math.min(90, v * multiplier));
  const line = pts.map((v, i) => `${i * (600 / (pts.length - 1))},${160 - v * 1.35}`).join(" ");
  return <div className="chart-wrap">
    <svg className="chart" viewBox="0 0 600 190" role="img" aria-label={`Tremor activity for ${range}`}>
      {[30,70,110,150].map(y => <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="#E7DCC0" strokeDasharray="4 6"/>)}
      {area && <polygon points={`0,170 ${line} 600,170`} fill="url(#area)" opacity=".55"/>}
      <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stopColor={C.lavender}/><stop offset="1" stopColor={C.cream}/></linearGradient></defs>
      {medication && [30,300,535].map((x, i) => <g key={x}><line x1={x} x2={x} y1="12" y2="168" stroke={C.orange} strokeWidth="3" strokeDasharray="5 5"/><circle cx={x} cy="16" r="9" fill={C.orange}/><text x={x} y="20" textAnchor="middle" fontSize="10">+</text><title>{["8:02 AM", "12:04 PM", "4:00 PM"][i]} medication</title></g>)}
      <polyline points={line} fill="none" stroke={C.purple} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
      {pts.map((v, i) => <circle className="chart-point" key={i} cx={i * (600 / (pts.length - 1))} cy={160 - v * 1.35} r="5" fill={C.purple}><title>{`${8 + i}:00 · ${Math.round(v)}% intensity · ${(4.3 + i % 5 * .15).toFixed(1)} Hz`}</title></circle>)}
      {["8 AM","10 AM","12 PM","2 PM","4 PM","6 PM","8 PM"].map((t,i) => <text key={t} x={i*100} y="187" fill="#736D63" fontSize="11">{t}</text>)}
    </svg>
  </div>;
}

function MiniBars({ values = [42,58,35,72,49,66,38], labels = false }: { values?: number[]; labels?: boolean }) {
  return <div className="bar-chart">{values.map((v, i) => <div className="bar-col" key={i}><div className="bar" style={{ height: `${v}%` }} title={`${v} episodes`} />{labels && <small>{["M","T","W","T","F","S","S"][i]}</small>}</div>)}</div>;
}

function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className={`modal ${wide ? "wide" : ""}`} onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}><div className="modal-head"><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="close"/></button></div>{children}</div></div>;
}

function Wristband({ connected = true }: { connected?: boolean }) {
  return <WristbandViewer className="wristband-art" connected={connected}/>;
}

function Auth({ route, go, enter }: { route: Route; go: (r: Route) => void; enter: (role: Role) => void }) {
  if (route === "landing") return <Landing go={go}/>;
  if (route === "setup") return <Onboarding enter={enter}/>;
  const copy: Record<string, [string,string]> = {
    login: ["Welcome back", "Log in to see your latest insights."], signup: ["Create your account", "Start understanding the pattern."],
    forgot: ["Forgot password?", "We'll send a secure reset link."], reset: ["Create a new password", "Choose a secure password you haven't used before."],
    verify: ["Check your inbox", "We sent a verification link to maria@example.com."],
  };
  const [title, sub] = copy[route] || copy.login;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (route === "login") enter("patient");
    else if (route === "signup") go("verify");
    else if (route === "verify") go("setup");
    else if (route === "forgot") go("reset");
    else go("login");
  };
  return <main className="auth-shell">
    <aside className="auth-brand"><Logo light/><div><h1>Your health data,<br/><em>beautifully organized.</em></h1><p>See the pattern. Understand the tremor.</p></div><div className="auth-wave">∿ ∿ ∿ ∿ ∿</div></aside>
    <section className="auth-panel"><button className="back-link" onClick={() => go("landing")}>← Back to home</button><form className="auth-card" onSubmit={submit}><span className="eyebrow">QUELL SECURE ACCESS</span><h2>{title}</h2><p>{sub}</p>
      {route !== "verify" && <><Field label="Email" type="email" placeholder="you@example.com"/>{route !== "forgot" && <Field label={route === "reset" ? "New password" : "Password"} type="password" placeholder="••••••••"/>}</>}
      {route === "login" && <div className="form-row"><label><input type="checkbox"/> Remember me</label><button type="button" className="text-link" onClick={() => go("forgot")}>Forgot password?</button></div>}
      <Button type="submit">{route === "login" ? "Log in" : route === "signup" ? "Create account" : route === "verify" ? "Verify & continue" : route === "forgot" ? "Send reset link" : "Reset password"}</Button>
      {route === "login" && <><div className="divider"><span>or use a demo</span></div><div className="demo-buttons"><Button variant="secondary" onClick={() => enter("patient")}>Continue as Patient</Button><Button variant="secondary" onClick={() => enter("clinician")}>Continue as Clinician</Button></div><p className="center">Don't have an account? <button type="button" className="text-link" onClick={() => go("signup")}>Create account</button></p></>}
    </form></section>
  </main>;
}

function Landing({ go }: { go: (r: Route) => void }) {
  return <main className="landing"><nav className="landing-nav"><Logo/><div className="landing-links"><button onClick={() => document.getElementById("platform")?.scrollIntoView({behavior:"smooth"})}>Platform</button><button onClick={() => document.getElementById("how")?.scrollIntoView({behavior:"smooth"})}>How it works</button><Button variant="ghost" onClick={() => go("login")}>Log in</Button><Button onClick={() => go("signup")}>Feel the Relief</Button></div></nav>
    <section className="hero"><div className="hero-copy"><Badge tone="purple">Targeted care for active symptom relief</Badge><h1>Quell the tremor.<br/><em>Restore your rhythm.</em></h1><p>A gentle therapeutic wristband that senses tremor patterns and delivers calming micro-vibrations to quiet tremors before they disrupt your day.</p><div className="hero-actions"><Button onClick={() => go("signup")}>Feel the Relief <Icon name="arrow" size={17}/></Button><Button variant="secondary" onClick={() => document.getElementById("platform")?.scrollIntoView({behavior:"smooth"})}>Explore the Platform</Button></div><small>Designed to soothe tremor symptoms and deliver clear relief patterns directly to your physician.</small></div>
      <div className="hero-visual"><div className="blob"/><Wristband/><div className="float-card detect"><span className="pulse-dot"/><small>TREMOR DETECTED</small><strong>4.7 Hz</strong></div><div className="float-card medicine"><Icon name="pill"/><span><small>MEDICATION RECORDED</small><strong>8:02 AM</strong></span></div><div className="float-card response"><small>MEASURED THERAPY RESPONSE</small><strong>−32%</strong><span>tremor intensity</span></div></div>
    </section>
    <section className="trust-strip"><span>One connected view</span><strong>Active relief</strong><i/> <strong>Symptom quelling</strong><i/> <strong>Relief duration</strong><i/> <strong>Care collaboration</strong></section>
    <section id="platform" className="feature-section"><div className="section-heading"><span className="eyebrow">THE COMPLETE PICTURE</span><h2>One device. Active relief for you, clear evidence for your doctor.</h2><p>Gentle, automatic vibrations that soothe tremors during your day, paired with clear data your physician can trust.</p></div><div className="feature-grid">
      <Card className="feature-card patient-feature"><span className="feature-icon"><Icon name="user"/></span><Badge>For you & your family</Badge><h3>Your day, made steadier.</h3><p>Feel tremor episodes soften with gentle vibrations, log your doses in one tap, and enjoy more steady hours without confusing charts.</p><div className="fake-score"><span><small>DAILY STABILITY SCORE</small><strong>82 <i>/ 100</i></strong></span><div className="score-ring">82</div></div></Card>
      <Card className="feature-card clinician-feature"><span className="feature-icon"><Icon name="chart"/></span><Badge tone="orange">For clinicians</Badge><h3>Patterns worth reviewing.</h3><p>Explore medication response, possible wearing-off patterns, and measured therapy outcomes.</p><TremorHeatmap/></Card>
    </div></section>
    <section id="how" className="steps-section"><div className="section-heading"><span className="eyebrow">HOW QUELL WORKS</span><h2>From a moment on the wrist<br/>to a pattern you can understand and improved relief you can feel.</h2></div><div className="steps">{[["01","Wear","The wristband continuously monitors movement to catch resting tremors the moment they begin."],["02","Measure","Episodes, frequency, duration, and therapy response are organized."],["03","Treat","Shared insights support more informed conversations."]].map(x=><div className="step" key={x[0]}><b>{x[0]}</b><h3>{x[1]}</h3><p>{x[2]}</p></div>)}</div></section>
    <footer><Logo light/><p>See the pattern. Understand the tremor.</p><Button onClick={() => go("signup")}>Get started</Button></footer>
  </main>;
}

function Onboarding({ enter }: { enter: (r: Role) => void }) {
  const [step, setStep] = useState(1); const [role, setRole] = useState<Role>("patient"); const [pairState, setPairState] = useState("Pair Device");
  const pair = () => { setPairState("Searching..."); setTimeout(() => setPairState("Connecting..."), 700); setTimeout(() => setPairState("Connected ✓"), 1500); };
  return <main className="onboarding"><div className="onboard-top"><Logo/><div className="progress">{[1,2,3,4,5].map(n=><span key={n} className={n<=step?"done":""}>{n<step?<Icon name="check" size={14}/>:n}</span>)}</div><small>Step {step} of 5</small></div><Card className="onboard-card">
    {step===1&&<><span className="eyebrow">LET'S GET TO KNOW YOU</span><h1>Who are you?</h1><p>We'll shape the experience around what matters to you.</p><div className="role-grid">{[["patient","Patient","I'm monitoring my own health"],["patient","Caregiver","I'm helping someone I care for"],["clinician","Clinician","I support patients and review data"]].map(([r,t,d])=><button key={t} className={`role-card ${role===r&&t!=="Caregiver"?"selected":""}`} onClick={()=>setRole(r as Role)}><Icon name={r==="clinician"?"users":"user"} size={26}/><strong>{t}</strong><span>{d}</span></button>)}</div></>}
    {step===2&&<><span className="eyebrow">YOUR PROFILE</span><h1>Tell us about yourself.</h1><div className="two-col"><Field label="First name" value="Maria"/><Field label="Last name" value="Chen"/><Field label="Date of birth" type="date"/><Field label="Primary neurologist" placeholder="Dr. Patel"/></div></>}
    {step===3&&<><span className="eyebrow">MEDICATION SETUP</span><h1>Add your medication.</h1><div className="two-col"><Field label="Medication name" value="Levodopa + Carbidopa"/><Field label="Dose" value="100 / 25 mg"/><Field label="Time" type="time"/><Field label="Frequency" value="4 times daily"/></div><Button variant="secondary" icon="plus">Add another medication</Button></>}
    {step===4&&<div className="pair-step"><Wristband connected={pairState==="Connected ✓"}/><div><span className="eyebrow">CONNECT YOUR WRISTBAND</span><h1>Calibrate Your Calm.</h1><p>Keep your wristband nearby. Pairing usually takes less than a minute.</p><Button onClick={pair} disabled={pairState!=="Pair Device"&&pairState!=="Connected ✓"}>{pairState}</Button></div></div>}
    {step===5&&<div className="complete-step"><span className="complete-icon"><Icon name="check" size={30}/></span><h1>You're all set.</h1><p>Your Quell wristband and medication schedule are ready. Let's take a look at your day.</p><Button onClick={()=>enter(role)}>Go to Dashboard</Button></div>}
    {step<5&&<div className="onboard-actions"><Button variant="ghost" onClick={()=>setStep(Math.max(1,step-1))}>Back</Button><Button onClick={()=>setStep(step+1)}>Continue <Icon name="arrow" size={16}/></Button></div>}
  </Card></main>;
}

const patientNav = [["dashboard","dashboard","Dashboard"],["medication","pill","Medication"],["tremors","wave","Tremors"],["timeline","clock","Timeline"],["therapy","spark","Therapy"],["safety","bell","Help & contacts"],["device","watch","Device"],["profile","user","Profile"]];
const clinicianNav = [["dashboard","dashboard","Dashboard"],["patients","users","Patients"],["analytics","chart","Analytics"],["medication","pill","Medication"],["therapy","spark","Therapy"],["safety","bell","Care alerts"],["reports","file","Reports"],["notes","note","Notes"],["settings","settings","Settings"]];

function Shell({ role, route, go, switchRole, logout, children, notifications, readNotification, markAll }: { role: Role; route: Route; go: (r: Route) => void; switchRole: () => void; logout: () => void; children: ReactNode; notifications: {id:number;text:string;read:boolean}[]; readNotification:(id:number)=>void; markAll:()=>void }) {
  const [open, setOpen] = useState(false); const [profile, setProfile] = useState(false); const [mobile, setMobile] = useState(false);
  const nav = role === "patient" ? patientNav : clinicianNav; const unread = notifications.filter(n=>!n.read).length;
  return <div className="app-shell"><aside className={`sidebar ${mobile?"show":""}`}><Logo light/><button className="mobile-close" onClick={()=>setMobile(false)}><Icon name="close"/></button><nav>{nav.map(([r,i,l])=><button key={r} className={route===r?"active":""} onClick={()=>{go(r as Route);setMobile(false)}}><Icon name={i}/><span>{l}</span></button>)}</nav><div className="side-bottom"><button onClick={switchRole}><Icon name="users"/><span>Switch to {role==="patient"?"clinician":"patient"}</span></button><button onClick={logout}><Icon name="logout"/><span>Log out</span></button><div className="side-profile"><div className="avatar">{role==="patient"?"MC":"DP"}</div><span><strong>{role==="patient"?"Maria Chen":"Dr. Anika Patel"}</strong><small>{role==="patient"?"Patient":"Neurologist"}</small></span></div></div></aside>
    <div className="app-main"><header className="topbar"><button className="menu-btn" onClick={()=>setMobile(true)}><Icon name="menu"/></button><div className="top-status">{role==="patient"?<Badge tone="success">● Wristband connected</Badge>:<Badge tone="purple">12 patients</Badge>}</div><div className="top-actions"><div className="popover-wrap"><button className="icon-btn" onClick={()=>setOpen(!open)} aria-label="Notifications"><Icon name="bell"/>{unread>0&&<i className="notify-count">{unread}</i>}</button>{open&&<div className="notification-pop"><div><h3>Notifications</h3><button className="text-link" onClick={markAll}>Mark all as read</button></div>{notifications.map(n=><button key={n.id} className={n.read?"read":""} onClick={()=>readNotification(n.id)}><i/><span>{n.text}<small>Today</small></span></button>)}</div>}</div><div className="popover-wrap"><button className="profile-button" onClick={()=>setProfile(!profile)}><div className="avatar">{role==="patient"?"MC":"DP"}</div><span>{role==="patient"?"Maria":"Dr. Patel"}</span><b>⌄</b></button>{profile&&<div className="profile-pop"><button onClick={()=>go(role==="patient"?"profile":"settings")}><Icon name="settings" size={17}/> Settings</button><button onClick={switchRole}><Icon name="users" size={17}/> Switch experience</button><button onClick={logout}><Icon name="logout" size={17}/> Log out</button></div>}</div></div></header><main className="page">{children}</main></div>
    <nav className="mobile-nav">{nav.slice(0,5).map(([r,i,l])=><button key={r} className={route===r?"active":""} onClick={()=>go(r as Route)}><Icon name={i}/><small>{l}</small></button>)}</nav>
  </div>;
}

function PageHead({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) { return <div className="page-head"><div><h1>{title}</h1>{sub&&<p>{sub}</p>}</div>{children&&<div className="page-actions">{children}</div>}</div>; }
function Metric({ icon, label, value, detail, tone = "" }: { icon?:string; label:string; value:string; detail?:string; tone?:string }) { return <Card className={`metric ${tone}`}>{icon&&<span className="metric-icon"><Icon name={icon}/></span>}<span>{label}</span><strong>{value}</strong>{detail&&<small>{detail}</small>}</Card>; }

function PatientDashboard({ meds, logMed, go, toast, openEvent }: { meds:Medication[]; logMed:(m:Medication)=>void; go:(r:Route)=>void; toast:(s:string)=>void; openEvent:(s:string)=>void }) {
  const [date,setDate]=useState("Today, October 8");
  return <><PageHead title="Good morning, Maria" sub="Here's how you're doing today."><select value={date} onChange={e=>setDate(e.target.value)}><option>Today, October 8</option><option>Yesterday, October 7</option><option>Monday, October 6</option></select></PageHead>
    <div className="dashboard-hero"><Card className="control-card"><div><span className="eyebrow">DAILY STABILITY SCORE</span><h2>Today's control</h2><p>Your tremor activity is currently below your 7-day average.</p><Badge tone="success">Good</Badge></div><div className="big-ring"><span><strong>82</strong><small>/ 100</small></span></div><i className="deco-wave">∿∿∿∿</i></Card><Card className="next-dose"><span className="metric-icon"><Icon name="pill"/></span><div><span>Next medication</span><strong>4:00 PM</strong><small>Levodopa + Carbidopa · 100 / 25 mg</small></div><Button onClick={()=>logMed(meds.find(m=>m.status==="Upcoming")!)}>Log dose</Button></Card></div>
    <div className="dashboard-grid"><Card className="med-card"><div className="card-head"><div><h2>Today's medication</h2><p>{meds.filter(m=>m.status==="Taken").length} of {meds.length} doses recorded</p></div><button className="text-link" onClick={()=>go("medication")}>View schedule →</button></div><div className="dose-list">{meds.map(m=><div className="dose" key={m.id}><span className={`dose-dot ${m.status==="Taken"?"taken":""}`}>{m.status==="Taken"?<Icon name="check" size={14}/>:<Icon name="clock" size={14}/>}</span><div><strong>{m.time}</strong><small>{m.name} · {m.dose}</small></div><Badge tone={m.status==="Taken"?"success":"warning"}>{m.status}</Badge>{m.status==="Upcoming"&&<button className="mini-btn" onClick={()=>logMed(m)}>Log dose</button>}</div>)}</div></Card>
      <Card className="tremor-card"><div className="card-head"><div><h2>Tremor activity</h2><p>Automatically recorded today</p></div><span className="wave-icon"><Icon name="wave"/></span></div><strong className="episode-count">3 <small>episodes today</small></strong><LineChart range="Today" area/><div className="three-stats"><span><small>AVG. DURATION</small><strong>1m 24s</strong></span><span><small>AVG. FREQUENCY</small><strong>4.7 Hz</strong></span><span><small>PEAK INTENSITY</small><strong>68%</strong></span></div><Button variant="secondary" onClick={()=>go("tremors")}>View tremor details</Button></Card>
    </div>
    <Card className="timeline-card"><div className="card-head"><div><h2>Today's timeline</h2><p>Medication, tremor, and therapy in one view</p></div><button className="text-link" onClick={()=>go("timeline")}>Full timeline →</button></div><div className="timeline-row">{[["8:00","Medication","pill"],["9:00","Stable","check"],["10:14","Tremor detected","wave"],["10:15","Therapy","spark"],["10:16","Tremor reduced","check"],["12:00","Medication","pill"],["1:38","Tremor detected","wave"]].map((e,i)=><button onClick={()=>openEvent(e[1])} className="timeline-event" key={i}><span className={`event-icon e${i}`}><Icon name={e[2]} size={17}/></span><strong>{e[0]}</strong><small>{e[1]}</small></button>)}</div></Card>
    <div className="quick-actions"><button onClick={()=>go("symptoms")}><Icon name="plus"/><span><strong>Log how you feel</strong><small>Share symptoms with your care team</small></span></button><button onClick={()=>go("safety")}><Icon name="bell"/><span><strong>Request help</strong><small>Contact your selected care network</small></span></button><button onClick={()=>{toast("Device synced · 14 new events added");go("device")}}><Icon name="watch"/><span><strong>Sync your wristband</strong><small>Last synced just now</small></span></button></div>
  </>;
}

function TremorsPage({ go, openEpisode }: { go:(r:Route)=>void; openEpisode:(e:typeof episodes[0])=>void }) {
  const [range,setRange]=useState("Today");
  return <><PageHead title="Tremors" sub="Understand when tremors happen and how they change throughout your day."/><Tabs items={["Today","7 days","30 days","Custom"]} value={range} onChange={setRange}/><Card className="large-chart-card"><div className="card-head"><div><h2>Tremor intensity</h2><p>Medication markers are shown in orange</p></div><div className="legend"><span className="purple-line"/> Tremor intensity <span className="orange-mark"/> Medication</div></div><LineChart range={range} medication/><div className="chart-caption"><span>Low activity</span><span>Hover over points for details</span><span>Higher activity</span></div></Card>
    <Card><div className="card-head"><div><h2>Tremor episodes</h2><p>{range==="Today"?"3 episodes":"47 episodes"} in selected period</p></div><Button variant="ghost" onClick={()=>go("timeline")}>View timeline</Button></div><div className="table-scroll"><table><thead><tr><th>Time</th><th>Duration</th><th>Frequency</th><th>Intensity</th><th>Therapy</th><th>Response</th><th></th></tr></thead><tbody>{episodes.map(e=><tr key={e.time} onClick={()=>openEpisode(e)}><td><strong>{e.time}</strong></td><td>{e.duration}</td><td>{e.frequency}</td><td><div className="intensity"><span><i style={{width:`${e.intensity}%`}}/></span>{e.intensity}%</div></td><td><Badge tone="purple">Activated</Badge></td><td><strong className="good">{e.response}</strong></td><td><Icon name="arrow" size={16}/></td></tr>)}</tbody></table></div></Card></>;
}

function MedicationPage({ meds, setMeds, logMed, openAdd, toast }: { meds:Medication[]; setMeds:(m:Medication[])=>void; logMed:(m:Medication)=>void; openAdd:()=>void; toast:(s:string)=>void }) {
  const remove=(id:number)=>{setMeds(meds.filter(m=>m.id!==id));toast("Medication removed")};
  return <><PageHead title="Medication" sub="Keep your schedule clear and your care team informed."><Button icon="plus" onClick={openAdd}>Add medication</Button></PageHead><Card className="schedule-card"><div className="card-head"><div><h2>Today's schedule</h2><p>Tuesday, October 8 · {meds.filter(m=>m.status==="Taken").length} of {meds.length} taken</p></div><Badge tone="success">94% adherence this month</Badge></div><div className="schedule">{meds.map((m,i)=><div className="schedule-item" key={m.id}><div className={`schedule-time ${m.status==="Taken"?"done":""}`}><span>{m.status==="Taken"?<Icon name="check"/>:<Icon name="clock"/>}</span>{i<meds.length-1&&<i/>}</div><div className="schedule-info"><span>{m.time}</span><h3>{m.name}</h3><p>{m.dose} · Scheduled {m.time}</p>{m.actual&&<div className="med-details"><span>Taken <strong>{m.actual}</strong></span><span>Response latency <strong>{m.latency}</strong> <abbr title="Time between medication intake and the observed reduction in tremor activity.">i</abbr></span></div>}</div><div className="schedule-actions"><Badge tone={m.status==="Taken"?"success":"warning"}>{m.status==="Taken"?"✓ Taken":"Upcoming"}</Badge>{m.status==="Upcoming"&&<Button onClick={()=>logMed(m)}>Log dose</Button>}<button className="text-link" onClick={()=>{const name=prompt("Medication name",m.name);if(name)setMeds(meds.map(x=>x.id===m.id?{...x,name}:x))}}>Edit</button><button className="text-link danger-text" onClick={()=>remove(m.id)}>Delete</button></div></div>)}</div></Card></>;
}

function SymptomsPage({ toast }: { toast:(s:string)=>void }) {
  const items=["Tremor","Stiffness","Slowness","Balance","Fatigue","Sleep","Mood","Cognition"]; const [ratings,setRatings]=useState<Record<string,string>>({Tremor:"Mild",Fatigue:"Moderate"}); const [saved,setSaved]=useState(false);
  return <><PageHead title="How are you feeling?" sub="A quick check-in helps your care team understand the full picture."/><Card className="symptom-card"><h2>Today's symptoms</h2><p>Select the level that feels most accurate right now.</p><div className="symptom-grid">{items.map(item=><div className="symptom-item" key={item}><strong>{item}</strong><div>{["None","Mild","Moderate","Severe"].map(r=><button className={ratings[item]===r?"selected":""} onClick={()=>setRatings({...ratings,[item]:r})} key={r}>{r}</button>)}</div></div>)}</div><label className="field"><span>Add a note</span><textarea placeholder="Anything you'd like your care team to know?"/></label><Button onClick={()=>{setSaved(true);toast("Symptoms saved")}}>Save symptoms</Button>{saved&&<div className="saved-state"><Icon name="check"/> Today's check-in was shared with your care team.</div>}</Card></>;
}

function TimelinePage({ openEvent }: { openEvent:(s:string)=>void }) {
  const events=[["8:02 AM","Medication recorded","Levodopa + Carbidopa · 100 / 25 mg","pill"],["9:00 AM","Stable period","Tremor activity remained low","check"],["10:14 AM","Tremor detected","42 sec · 4.6 Hz · 42% peak intensity","wave"],["10:15 AM","Therapeutic vibration","Patterned vibration activated automatically","spark"],["10:16 AM","Measured reduction","21% lower tremor intensity after activation","chart"],["12:04 PM","Medication recorded","Levodopa + Carbidopa · 100 / 25 mg","pill"],["1:38 PM","Tremor detected","1m 21s · 4.8 Hz · 68% peak intensity","wave"]];
  return <><PageHead title="Timeline" sub="A chronological view of medication, movement, and therapy."/><Tabs items={["Today","Yesterday","7 days"]} value="Today" onChange={()=>{}}/><Card className="vertical-timeline">{events.map((e,i)=><button key={i} onClick={()=>openEvent(e[1])}><time>{e[0]}</time><span className="event-icon"><Icon name={e[3]}/></span><div><strong>{e[1]}</strong><p>{e[2]}</p></div><Icon name="arrow"/></button>)}</Card></>;
}

function TherapyPage({ clinician=false }: { clinician?:boolean }) {
  const [range,setRange]=useState("7 days");
  return <><PageHead title={clinician?"Therapy analytics":"Therapy"} sub={clinician?"Review measured response to patterned vibration.":"See how your wristband's therapeutic vibrations have responded to tremor episodes."}/><Tabs items={["Today","7 days","30 days"]} value={range} onChange={setRange}/><div className="metric-grid four"><Metric label={clinician?"Episodes treated":"Therapy sessions today"} value={clinician?"32":"3"} icon="spark"/><Metric label={clinician?"Observed response rate":"Average response"} value={clinician?"69%":"−24%"} detail="Measured change"/><Metric label={clinician?"Average measured reduction":"Best response"} value={clinician?"24%":"−32%"}/><Metric label="Total vibration time" value={clinician?"28m 42s":"3m 12s"}/></div>
    <div className="two-panel"><Card className="before-after"><h2>Measured therapy response</h2><p>Average tremor intensity before and after vibration activation.</p><div className="response-visual"><div><span style={{height:"68%"}}/><strong>68%</strong><small>Before</small></div><span className="response-arrow">→<small>Vibration activation</small></span><div><span className="after" style={{height:"46%"}}/><strong>46%</strong><small>After</small></div></div><div className="measured-change"><Icon name="chart"/><span><small>MEASURED CHANGE</small><strong>−32%</strong></span></div></Card>
      <Card><h2>{clinician?"Response by episode intensity":"Recent therapy sessions"}</h2><p>{clinician?"Each point represents one treated episode.":"Measured changes are observations, not guaranteed outcomes."}</p>{clinician?<Scatter/>:<div className="session-list">{episodes.map(e=><div key={e.time}><span className="event-icon"><Icon name="spark"/></span><span><strong>{e.time}</strong><small>{e.duration} vibration</small></span><Badge tone="success">{e.response} measured</Badge></div>)}</div>}</Card></div>
    <div className="safety-note"><Icon name="spark"/><p><strong>About these measurements</strong> Quell tracks changes observed after vibration begins. Individual responses vary; review patterns with your clinician.</p></div></>;
}
function Scatter(){return <svg className="scatter" viewBox="0 0 400 220"><line x1="45" y1="10" x2="45" y2="185"/><line x1="45" y1="185" x2="390" y2="185"/>{[55,72,90,120,145,177,205,240,275,310,340].map((x,i)=><circle key={x} cx={x} cy={165-(i*17)%120} r="7" fill={i%3===0?C.orange:C.purple} opacity=".75"><title>Before: {40+i*4}% · Reduction: {10+i*3}%</title></circle>)}<text x="190" y="213">Intensity before therapy</text><text transform="rotate(-90 13 145)" x="13" y="145">Measured reduction</text></svg>}

function DevicePage({ toast }: { toast:(s:string)=>void }) {
  const [sync,setSync]=useState("Sync now"); const [paired,setPaired]=useState(true); const [error,setError]=useState(false);
  const doSync=()=>{setSync("Syncing device...");setTimeout(()=>{if(error){setSync("Try again");toast("We couldn't sync your wristband");}else{setSync("✓ Synced successfully");toast("Device synced · 14 new events added");}},1200)};
  if(!paired)return <><PageHead title="Your wristband"/><Card className="empty-state"><Icon name="watch" size={46}/><h2>No device connected</h2><p>Pair your Quell wristband to start recording movement patterns.</p><Button onClick={()=>{setPaired(true);toast("Wristband connected")}}>Pair device</Button></Card></>;
  return <><PageHead title="Your wristband" sub="Connected and keeping your day in sync."/><div className="device-layout"><Card className="device-visual"><Badge tone="success">● Connected</Badge><Wristband/><strong>Quell One</strong><small>Device ID · QLL-2048</small></Card><div className="device-info"><Card><div className="card-head"><h2>Device status</h2><Badge tone="success">All systems normal</Badge></div><div className="device-stats"><span><small>BATTERY</small><strong>78%</strong><i><b style={{width:"78%"}}/></i></span><span><small>LAST SYNCED</small><strong>Just now</strong></span><span><small>CONNECTION</small><strong>Excellent</strong></span><span><small>DATA</small><strong>Up to date</strong></span></div><div className="button-row"><Button onClick={doSync}>{sync}</Button><Button variant="secondary" onClick={()=>toast("Device test complete · All systems normal")}>Run device test</Button></div>{sync==="Try again"&&<div className="sync-error"><strong>We couldn't sync your wristband</strong><p>Check that your device is nearby and try again.</p></div>}</Card><Card><h2>Device controls</h2><Toggle label="Automatic therapy activation" value={true} onChange={()=>toast("Therapy setting updated")}/><Toggle label="Gentle medication reminder" value={true} onChange={()=>toast("Reminder setting updated")}/><button className="text-link danger-text" onClick={()=>setPaired(false)}>Unpair device</button><button className="hidden-test" onClick={()=>setError(!error)}>Toggle error simulation</button></Card></div></div></>;
}

function ClinicianDashboard({ go }: { go:(r:Route)=>void }) {
  return <><PageHead title="Good morning, Dr. Patel" sub="Patient monitoring overview"><Button variant="secondary" onClick={()=>go("reports")}>Generate report</Button></PageHead><div className="metric-grid four"><Metric icon="users" label="Patients monitored" value="12" detail="+2 this month"/><Metric icon="wave" label="Patients requiring review" value="3" detail="2 new since yesterday" tone="warm"/><Metric icon="chart" label="Avg. measured improvement" value="18%" detail="Across treated episodes"/><Metric icon="file" label="Reports generated" value="27" detail="This month"/></div><div className="clin-grid"><Card className="attention-card"><div className="card-head"><div><h2>Patients requiring attention</h2><p>Prioritized from recent monitoring signals</p></div><button className="text-link" onClick={()=>go("patients")}>View all patients →</button></div>{patients.slice(0,3).map((p,i)=><button className="attention-row" key={p.name} onClick={()=>go("patient")}><div className="avatar">{p.name.split(" ").map(x=>x[0]).join("")}</div><span><strong>{p.name}</strong><small>{i===0?"Possible wearing-off pattern":"Recent change in tremor activity"}</small></span><Badge tone={i===0?"warning":"neutral"}>{p.status}</Badge><span className="trend">{p.trend}</span><Icon name="arrow"/></button>)}</Card><Card className="overview-chart"><div className="card-head"><div><h2>Tremor activity overview</h2><p>Across monitored patients · 7 days</p></div><Badge tone="purple">All patients</Badge></div><MiniBars labels/><div className="chart-total"><strong>286</strong><span>episodes recorded<br/><b>↓ 6%</b> vs previous week</span></div></Card></div><Card className="insight-banner"><span className="insight-icon"><Icon name="spark"/></span><div><Badge tone="orange">PATTERN INSIGHT</Badge><h2>3 patients show a possible wearing-off pattern.</h2><p>Activity increased in the 30–45 minutes before scheduled medication across multiple observed days.</p></div><Button onClick={()=>go("analytics")}>Review patterns</Button></Card></>;
}

function PatientsPage({ go }: { go:(r:Route)=>void }) {
  const [search,setSearch]=useState("");const [filter,setFilter]=useState("All");const shown=patients.filter(p=>(filter==="All"||p.status===filter)&&p.name.toLowerCase().includes(search.toLowerCase()));
  return <><PageHead title="Patients" sub="Monitor sync status, trends, and recent clinical review."/><div className="list-tools"><label className="search"><Icon name="search"/><input placeholder="Search patients..." value={search} onChange={e=>setSearch(e.target.value)}/></label><Tabs items={["All","Needs review","Stable","Recent episode"]} value={filter} onChange={setFilter}/></div><Card className="patient-table"><div className="table-scroll"><table><thead><tr><th>Patient</th><th>Status</th><th>Last sync</th><th>Tremor trend</th><th>Medication adherence</th><th>Last review</th><th></th></tr></thead><tbody>{shown.map(p=><tr key={p.name} onClick={()=>go("patient")}><td><div className="patient-cell"><div className="avatar">{p.name.split(" ").map(x=>x[0]).join("")}</div><span><strong>{p.name}</strong><small>{p.age} years · Monitoring</small></span></div></td><td><Badge tone={p.status==="Stable"?"success":p.status==="Needs review"?"warning":"purple"}>{p.status}</Badge></td><td>{p.sync}</td><td><strong className={p.trend.includes("↑")?"danger-text":"good"}>{p.trend}</strong></td><td>{p.adherence}</td><td>{p.review}</td><td><Icon name="arrow"/></td></tr>)}</tbody></table></div>{!shown.length&&<div className="empty-state"><Icon name="users"/><h2>No patients found</h2><p>Try changing your search or filters.</p></div>}</Card></>;
}

function PatientOverview({ go, addNote }: { go:(r:Route)=>void; addNote:()=>void }) {
  return <><button className="back-link" onClick={()=>go("patients")}>← Back to patients</button><PageHead title="Maria Chen" sub="67 years · Parkinson's monitoring · Wristband connected"><Button variant="secondary" onClick={addNote}>Add note</Button><Button onClick={()=>go("reports")}>Generate report</Button></PageHead><div className="patient-banner"><div className="avatar big">MC</div><div><span>LAST SYNCED</span><strong>2 minutes ago</strong></div><div><span>MONITORING SINCE</span><strong>March 2024</strong></div><div><span>PRIMARY MEDICATION</span><strong>Levodopa + Carbidopa</strong></div><Badge tone="warning">Needs review</Badge></div><div className="metric-grid four"><Metric label="Tremor episodes" value="47" detail="Last 30 days"/><Metric label="Avg. frequency" value="4.7 Hz"/><Metric label="Avg. duration" value="1m 32s"/><Metric label="Medication adherence" value="94%"/></div><div className="two-panel"><Card className="large-chart-card"><div className="card-head"><div><h2>Medication & tremor activity</h2><p>Last 7 days · average daily profile</p></div><button className="text-link" onClick={()=>go("analytics")}>Open analytics →</button></div><LineChart range="7 days" medication/></Card><Card><h2>Recent observations</h2><div className="observation"><span className="insight-icon"><Icon name="spark"/></span><div><Badge tone="orange">POSSIBLE PATTERN</Badge><strong>Afternoon wearing-off</strong><p>Activity increased before the scheduled afternoon dose on 8 observed days.</p><button className="text-link" onClick={()=>go("analytics")}>Review with clinician →</button></div></div><div className="observation"><span className="insight-icon lavender"><Icon name="chart"/></span><div><Badge tone="purple">THERAPY RESPONSE</Badge><strong>69% observed response rate</strong><p>22 of 32 treated episodes showed measurable reduction.</p></div></div></Card></div></>;
}

function AnalyticsPage() {
  const [tab,setTab]=useState("Overview");const [range,setRange]=useState("30 days");const [cell,setCell]=useState<string|null>(null);
  return <><PageHead title="Analytics" sub="Explore longitudinal tremor, medication, and therapy patterns."><Tabs items={["7 days","14 days","30 days","90 days","Custom"]} value={range} onChange={setRange}/></PageHead><Tabs items={["Overview","Tremors","Medication","Therapy"]} value={tab} onChange={setTab}/>
    {tab==="Therapy"?<TherapyPage clinician/>:<><div className="metric-grid five"><Metric label="Total episodes" value={range==="7 days"?"12":"47"}/><Metric label="Average duration" value="1m 32s"/><Metric label="Average frequency" value="4.7 Hz"/><Metric label="Peak amplitude" value="8.4 °/s"/><Metric label="Most active time" value="3–5 PM"/></div><Card className="large-chart-card"><div className="card-head"><div><h2>{tab==="Medication"?"Medication vs. tremor activity":tab==="Tremors"?"Tremor intensity over time":"Tremor & medication overview"}</h2><p>Purple line shows tremor intensity · orange markers show medication intake</p></div><div className="legend"><span className="purple-line"/> Intensity <span className="orange-mark"/> Medication <span className="on-region"/> Estimated ON period</div></div><div className="on-off-labels"><span>Estimated ON period</span><span>Possible wearing-off period</span></div><LineChart range={range} medication/><p className="chart-disclaimer">Estimated periods are based on observed movement patterns and medication records. They are not a clinical determination.</p></Card>
    <div className="analytics-grid"><Card><h2>Episodes per day</h2><p>Daily count in selected period</p><MiniBars values={[35,62,45,74,58,41,69]} labels/></Card><Card><h2>Tremor frequency</h2><p>Average dominant frequency</p><div className="frequency-number"><strong>4.7</strong><span>Hz<br/><b>within recent range</b></span></div><LineChart range={range} area={false}/></Card></div>
    <Card className="wearing-card"><div className="wearing-copy"><Badge tone="orange">OBSERVED PATTERN</Badge><h2>Possible wearing-off pattern</h2><p>Across 8 observed days, tremor activity increased during the 30–45 minutes preceding the scheduled afternoon dose.</p><div><Badge tone="warning">Pattern confidence: Moderate</Badge><Button variant="secondary">Review with clinician</Button></div></div><div className="pattern-flow">{[["pill","Medication"],["chart","Improvement"],["check","Stable period"],["wave","Gradual increase"],["pill","Next medication"]].map((x,i)=><div key={x[1]}><span><Icon name={x[0]}/></span><small>{x[1]}</small>{i<4&&<i>→</i>}</div>)}</div></Card>
    <Card className="heatmap-card"><div className="card-head"><div><h2>Tremor power density</h2><p>Intensity patterns by date and time of day</p></div><div className="heat-legend">Low <i/><i/><i/><i/> Very high</div></div><div className="heatmap"><div className="heat-times"><span>6 AM</span><span>9 AM</span><span>12 PM</span><span>3 PM</span><span>6 PM</span><span>9 PM</span></div>{Array.from({length:10},(_,r)=><div className="heat-row" key={r}><small>Oct {r+1}</small>{Array.from({length:18},(_,i)=>{const level=(i*3+r*2+(i%5))%5;return <button aria-label={`October ${r+1}, ${6+Math.floor(i/3)} AM intensity level ${level}`} onClick={()=>setCell(`October ${r+1} · ${6+Math.floor(i/3)}:00 · ${level+1} episodes · ${35+level*11}% average intensity · ${(4.4+level*.15).toFixed(1)} Hz`)} key={i} className={`heat h${level}`}/>})}</div>)}</div>{cell&&<div className="cell-detail"><Icon name="wave"/><strong>Selected interval</strong><span>{cell}</span><button onClick={()=>setCell(null)}><Icon name="close" size={16}/></button></div>}</Card></>}</>;
}

function NotesPage({ notes,setNotes,toast }: { notes:Note[];setNotes:(n:Note[])=>void;toast:(s:string)=>void }) {
  const [text,setText]=useState("");const add=()=>{if(!text.trim())return;setNotes([{id:Date.now(),text,date:"Just now",pinned:false},...notes]);setText("");toast("Note added")};
  return <><PageHead title="Clinical notes" sub="Private notes for Maria Chen's care review."/><div className="notes-layout"><Card className="note-compose"><h2>Add a note</h2><label className="field"><span>Clinical observation</span><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Add an observation or follow-up reminder..."/></label><Button onClick={add}>Add note</Button></Card><div className="note-list">{notes.length?notes.sort((a,b)=>Number(b.pinned)-Number(a.pinned)).map(n=><Card className="note-card" key={n.id}>{n.pinned&&<Badge tone="purple">Pinned</Badge>}<p>{n.text}</p><small>{n.date} · Dr. Anika Patel</small><div><button className="text-link" onClick={()=>setNotes(notes.map(x=>x.id===n.id?{...x,pinned:!x.pinned}:x))}>{n.pinned?"Unpin":"Pin"}</button><button className="text-link" onClick={()=>{const t=prompt("Edit note",n.text);if(t)setNotes(notes.map(x=>x.id===n.id?{...x,text:t}:x))}}>Edit</button><button className="text-link danger-text" onClick={()=>{setNotes(notes.filter(x=>x.id!==n.id));toast("Note deleted")}}>Delete</button></div></Card>):<Card className="empty-state"><Icon name="note"/><h2>No notes yet</h2><p>Add a clinical observation to begin.</p></Card>}</div></div></>;
}

function ReportsPage({ toast }: { toast:(s:string)=>void }) {
  const [range,setRange]=useState("30 days"); const [sections,setSections]=useState(["Tremor summary","Medication timeline","Tremor frequency","Tremor intensity","Wearing-off analysis","Therapy effectiveness","Patient symptoms","Clinician notes"]); const [state,setState]=useState<"form"|"loading"|"ready"|"preview">("form");
  const toggle=(s:string)=>setSections(sections.includes(s)?sections.filter(x=>x!==s):[...sections,s]); const generate=()=>{setState("loading");setTimeout(()=>{setState("ready");toast("Report generated")},1400)};
  if(state==="preview")return <ReportPreview back={()=>setState("ready")}/>;
  return <><PageHead title="Generate Patient Report" sub="Create a clear, review-ready summary for Maria Chen."/>{state==="loading"?<Card className="report-loading"><div className="spinner"/><h2>Preparing report...</h2><p>Compiling tremor, medication, therapy, and symptom data.</p><div className="skeleton"/><div className="skeleton short"/></Card>:state==="ready"?<Card className="report-ready"><span><Icon name="check" size={34}/></span><h2>Report ready</h2><p>Maria Chen · {range} · {sections.length} sections</p><div className="button-row"><Button onClick={()=>setState("preview")}>View Report</Button><Button variant="secondary" icon="download" onClick={()=>{toast("PDF download started");window.print()}}>Download PDF</Button><Button variant="secondary" icon="print" onClick={()=>window.print()}>Print</Button><Button variant="secondary" onClick={()=>toast("Secure share link copied")}>Share</Button></div><button className="text-link" onClick={()=>setState("form")}>Create another report</button></Card>:<div className="report-builder"><div><Card><span className="step-label">1</span><h2>Date range</h2><Tabs items={["7 days","14 days","30 days","Custom"]} value={range} onChange={setRange}/></Card><Card><span className="step-label">2</span><h2>Choose sections</h2><div className="check-grid">{["Tremor summary","Medication timeline","Tremor frequency","Tremor intensity","Wearing-off analysis","Therapy effectiveness","Patient symptoms","Clinician notes"].map(s=><label key={s}><input type="checkbox" checked={sections.includes(s)} onChange={()=>toggle(s)}/><span><Icon name="check" size={14}/></span>{s}</label>)}</div></Card></div><Card className="report-summary"><span className="step-label">3</span><h2>Report summary</h2><div className="report-paper-mini"><Logo/><hr/><strong>Patient Tremor Monitoring Report</strong><p>Maria Chen · Sept 1–Sept 30</p>{sections.slice(0,5).map((s,i)=><span key={s}>{i+1}. {s}</span>)}</div><Button onClick={generate}>Generate Report</Button><small>Usually ready in a few seconds.</small></Card></div>}</>;
}

function ReportPreview({ back }: { back:()=>void }) {
  return <><PageHead title="Report preview"><Button variant="secondary" onClick={back}>Back</Button><Button icon="print" onClick={()=>window.print()}>Print report</Button></PageHead><article className="report-paper"><header><Logo/><div><strong>Patient Tremor Monitoring Report</strong><small>Generated October 8, 2025</small></div></header><div className="report-meta"><span><small>PATIENT</small><strong>Maria Chen</strong></span><span><small>REPORTING PERIOD</small><strong>Sept 1–Sept 30</strong></span><span><small>CLINICIAN</small><strong>Dr. Anika Patel</strong></span></div><section><span className="report-num">01</span><h2>Executive Summary</h2><p>During this reporting period, Quell recorded 47 tremor episodes with an average dominant frequency of 4.7 Hz. Medication adherence was 94%. A possible afternoon wearing-off pattern was observed for clinical review.</p><div className="report-metrics"><Metric label="Episodes" value="47"/><Metric label="Avg. frequency" value="4.7 Hz"/><Metric label="Adherence" value="94%"/><Metric label="Observed response" value="69%"/></div></section><section><span className="report-num">02</span><h2>Tremor & medication overview</h2><LineChart range="30 days" medication/></section><section><span className="report-num">03</span><h2>Observed patterns</h2><div className="report-callout"><strong>Possible wearing-off pattern</strong><p>On 8 observed days, activity increased 30–45 minutes before the scheduled afternoon dose. Pattern confidence: Moderate. Review with clinician.</p></div></section><section><span className="report-num">04</span><h2>Therapeutic vibration response</h2><p>32 episodes included therapeutic vibration. 22 showed a measurable reduction in tremor intensity after activation, with an average measured change of 24%.</p></section><footer>These measurements are intended to support clinical review and do not replace professional medical judgment.</footer></article></>;
}

function SettingsPage({ patient=false, toast }: { patient?:boolean;toast:(s:string)=>void }) {
  const [settings,setSettings]=useState({reminders:true,episodes:true,battery:true,weekly:false,contrast:false,large:false,motion:true});
  const tog=(k:keyof typeof settings)=>{setSettings({...settings,[k]:!settings[k]});toast("Setting updated")};
  return <><PageHead title={patient?"Profile & settings":"Settings"} sub="Manage your account, privacy, and experience."/><div className="settings-layout"><nav>{["Account","Notifications","Medication reminders","Device","Privacy","Security","Accessibility","Appearance"].map((x,i)=><button className={i===1?"active":""} key={x}>{x}</button>)}</nav><div><Card><h2>Notifications</h2><p>Choose what you'd like Quell to tell you about.</p><Toggle label="Medication reminders" value={settings.reminders} onChange={()=>tog("reminders")}/><Toggle label="New tremor episode summaries" value={settings.episodes} onChange={()=>tog("episodes")}/><Toggle label="Low device battery" value={settings.battery} onChange={()=>tog("battery")}/><Toggle label="Weekly report ready" value={settings.weekly} onChange={()=>tog("weekly")}/></Card><Card><h2>Accessibility</h2><p>Adjust Quell to make information easier to use.</p><Toggle label="Larger interface text" value={settings.large} onChange={()=>tog("large")}/><Toggle label="Increase contrast" value={settings.contrast} onChange={()=>tog("contrast")}/><Toggle label="Reduce motion" value={settings.motion} onChange={()=>tog("motion")}/></Card><Card><h2>Privacy & security</h2><div className="setting-link"><span><strong>Data sharing</strong><small>Manage access for your care team</small></span><Icon name="arrow"/></div><div className="setting-link"><span><strong>Password & authentication</strong><small>Last changed 3 months ago</small></span><Icon name="arrow"/></div></Card></div></div></>;
}

export default function App() {
  const [route,setRoute]=useState<Route>("landing"); const [role,setRole]=useState<Role>("patient"); const [authed,setAuthed]=useState(false); const [meds,setMeds]=useState(seedMeds); const [modal,setModal]=useState<{type:string;data?:any}|null>(null); const [toast,setToast]=useState(""); const [notes,setNotes]=useState<Note[]>([{id:1,text:"Patient reports increased tremor before afternoon dose.",date:"Oct 7, 3:42 PM",pinned:true},{id:2,text:"Review medication timing at next appointment.",date:"Oct 2, 10:15 AM",pinned:false}]);
  const [notifications,setNotifications]=useState([{id:1,text:"Medication reminder: Afternoon dose in 15 minutes.",read:false},{id:2,text:"New tremor episode detected.",read:false},{id:3,text:"Weekly report is ready.",read:true},{id:4,text:"Your wristband synced successfully.",read:true}]);
  const showToast=(s:string)=>{setToast(s);setTimeout(()=>setToast(""),2600)}; const addNotification=(text:string)=>setNotifications(current=>[{id:Date.now(),text,read:false},...current]); const go=(r:Route)=>{setRoute(r);window.scrollTo(0,0)}; const enter=(r:Role)=>{setRole(r);setAuthed(true);go("dashboard")}; const logout=()=>{setAuthed(false);go("landing")};
  const logMed=(m:Medication)=>m&&setModal({type:"med",data:m}); const confirmMed=()=>{const m=modal?.data as Medication;setMeds(meds.map(x=>x.id===m.id?{...x,status:"Taken",actual:"4:03 PM",latency:"Pending"}:x));setModal(null);showToast("Medication recorded at 4:03 PM")};
  const content=useMemo(()=>{
    if(role==="patient"){
      if(route==="dashboard")return <PatientDashboard meds={meds} logMed={logMed} go={go} toast={showToast} openEvent={s=>setModal({type:"event",data:s})}/>;
      if(route==="medication")return <MedicationPage meds={meds} setMeds={setMeds} logMed={logMed} openAdd={()=>setModal({type:"add-med"})} toast={showToast}/>;
      if(route==="tremors")return <TremorsPage go={go} openEpisode={e=>setModal({type:"episode",data:e})}/>;
      if(route==="symptoms")return <SymptomsPage toast={showToast}/>;
      if(route==="timeline")return <TimelinePage openEvent={s=>setModal({type:"event",data:s})}/>;
      if(route==="therapy")return <TherapyPage/>;
      if(route==="safety")return <CareSafety role="patient" toast={showToast} notify={addNotification}/>;
      if(route==="device")return <DevicePage toast={showToast}/>;
      return <SettingsPage patient toast={showToast}/>;
    }
    if(route==="dashboard")return <ClinicianDashboard go={go}/>;
    if(route==="patients")return <PatientsPage go={go}/>;
    if(route==="patient")return <PatientOverview go={go} addNote={()=>setModal({type:"note"})}/>;
    if(route==="analytics"||route==="medication")return <AnalyticsPage/>;
    if(route==="therapy")return <TherapyPage clinician/>;
    if(route==="safety")return <CareSafety role="clinician" toast={showToast} notify={addNotification}/>;
    if(route==="reports")return <ReportsPage toast={showToast}/>;
    if(route==="notes")return <NotesPage notes={notes} setNotes={setNotes} toast={showToast}/>;
    return <SettingsPage toast={showToast}/>;
  },[role,route,meds,notes]);
  if(!authed)return <Auth route={route} go={go} enter={enter}/>;
  return <><Shell role={role} route={route} go={go} switchRole={()=>{setRole(role==="patient"?"clinician":"patient");go("dashboard");showToast(`Switched to ${role==="patient"?"clinician":"patient"} experience`)}} logout={logout} notifications={notifications} readNotification={id=>setNotifications(notifications.map(n=>n.id===id?{...n,read:true}:n))} markAll={()=>setNotifications(notifications.map(n=>({...n,read:true})))}>{content}</Shell>
    {modal?.type==="med"&&<Modal title="Record medication" onClose={()=>setModal(null)}><div className="confirm-med"><span className="modal-icon"><Icon name="pill"/></span><dl><div><dt>Medication</dt><dd>{modal.data.name}</dd></div><div><dt>Dose</dt><dd>{modal.data.dose}</dd></div><div><dt>Time</dt><dd>4:03 PM</dd></div></dl><div className="modal-actions"><Button variant="ghost" onClick={()=>setModal(null)}>Cancel</Button><Button onClick={confirmMed}>Confirm</Button></div></div></Modal>}
    {modal?.type==="episode"&&<Modal title="Tremor episode" wide onClose={()=>setModal(null)}><div className="episode-detail"><div className="detail-grid">{[["Start",modal.data.start],["End",modal.data.end],["Duration",modal.data.duration],["Dominant frequency",modal.data.frequency],["Peak rotational amplitude","8.4 °/s"],["Therapeutic vibration","Activated"],["Vibration onset","1:38:12 PM"],["Measured response",modal.data.response]].map(x=><span key={x[0]}><small>{x[0]}</small><strong>{x[1]}</strong></span>)}</div><div className="episode-flow">{["Tremor begins","Vibration begins","Tremor decreases","Episode ends"].map((x,i)=><div key={x}><span className={i===2?"success":""}><Icon name={i===1?"spark":i===2?"chart":"wave"}/></span><strong>{x}</strong>{i<3&&<i>↓</i>}</div>)}</div><p className="chart-disclaimer">Measured response describes observed sensor data and does not indicate a guaranteed therapeutic outcome.</p></div></Modal>}
    {modal?.type==="event"&&<Modal title={modal.data} onClose={()=>setModal(null)}><div className="event-modal"><span className="modal-icon"><Icon name="clock"/></span><h3>Today · 10:14 AM</h3><p>This event was recorded automatically by your Quell wristband and added to today's timeline.</p><Button onClick={()=>setModal(null)}>Done</Button></div></Modal>}
    {modal?.type==="add-med"&&<AddMedication onClose={()=>setModal(null)} onSave={(m)=>{setMeds([...meds,{id:Date.now(),...m,status:"Upcoming"}]);setModal(null);showToast("Medication added")}}/>}
    {modal?.type==="note"&&<AddNote onClose={()=>setModal(null)} onSave={text=>{setNotes([{id:Date.now(),text,date:"Just now",pinned:false},...notes]);setModal(null);showToast("Note added")}}/>}
    {toast&&<div className="toast"><Icon name={toast.includes("couldn't")?"wave":"check"}/>{toast}</div>}</>;
}

function AddMedication({onClose,onSave}:{onClose:()=>void;onSave:(m:Omit<Medication,"id"|"status">)=>void}){const [name,setName]=useState("");const [dose,setDose]=useState("");const [time,setTime]=useState("");return <Modal title="Add medication" onClose={onClose}><div className="modal-form"><Field label="Medication name" value={name} onChange={setName} placeholder="Medication name"/><Field label="Dose" value={dose} onChange={setDose} placeholder="e.g. 100 / 25 mg"/><Field label="Time" type="time" value={time} onChange={setTime}/><Field label="Frequency" placeholder="e.g. Daily"/><div className="modal-actions"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!name||!dose||!time} onClick={()=>onSave({name,dose,time})}>Save medication</Button></div></div></Modal>}
function AddNote({onClose,onSave}:{onClose:()=>void;onSave:(s:string)=>void}){const [text,setText]=useState("");return <Modal title="Add clinician note" onClose={onClose}><label className="field"><span>Clinical note</span><textarea value={text} onChange={e=>setText(e.target.value)} placeholder="Add an observation or follow-up reminder..."/></label><div className="modal-actions"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!text.trim()} onClick={()=>onSave(text)}>Save note</Button></div></Modal>}

import React from "react";
import {
  AlertTriangle,
  Plane,
  ScanSearch,
  Bell,
  BatteryMedium,
  Signal,
  Flame,
  Droplets,
  Building2,
} from "lucide-react";
import DroneMap from "../Map/DroneMap";

/* ---------- placeholder data ---------- */
const STATS = [
  { label: "Active Incidents", value: 3,    icon: AlertTriangle, color: "text-fire-red",   bg: "bg-fire-red/10" },
  { label: "Drones Flying",    value: 7,    icon: Plane,         color: "text-sky-400",     bg: "bg-sky-400/10" },
  { label: "Detections Today", value: 142,  icon: ScanSearch,    color: "text-amber-400",   bg: "bg-amber-400/10" },
  { label: "Active Alerts",    value: 5,    icon: Bell,          color: "text-rose-400",    bg: "bg-rose-400/10" },
];

const ALERTS = [
  { id: 1, severity: "critical", text: "Fire spread detected NE sector - Incident #1042",   time: "2m ago",  icon: Flame,    color: "text-fire-red" },
  { id: 2, severity: "warning",  text: "Drone ALPHA-03 battery below 25%",                   time: "5m ago",  icon: BatteryMedium, color: "text-amber-400" },
  { id: 3, severity: "critical", text: "Flood water rising at Checkpoint Bravo",             time: "8m ago",  icon: Droplets, color: "text-water-blue" },
  { id: 4, severity: "info",     text: "Structural damage confirmed at 42nd & Main",         time: "12m ago", icon: Building2, color: "text-amber-400" },
  { id: 5, severity: "warning",  text: "EMQX connection latency > 500ms",                    time: "15m ago", icon: Signal,   color: "text-amber-400" },
];

const FLEET = [
  { callsign: "ALPHA-01", status: "flying",  battery: 82, mission: "Incident #1042" },
  { callsign: "ALPHA-02", status: "flying",  battery: 64, mission: "Incident #1042" },
  { callsign: "ALPHA-03", status: "flying",  battery: 23, mission: "Incident #1042" },
  { callsign: "BRAVO-01", status: "flying",  battery: 91, mission: "Incident #1038" },
  { callsign: "BRAVO-02", status: "flying",  battery: 77, mission: "Incident #1038" },
  { callsign: "CHARLIE-01", status: "flying", battery: 55, mission: "Patrol Zone C" },
  { callsign: "CHARLIE-02", status: "flying", battery: 48, mission: "Patrol Zone C" },
  { callsign: "DELTA-01",  status: "standby", battery: 100, mission: "\u2014" },
  { callsign: "DELTA-02",  status: "offline", battery: 0,   mission: "\u2014" },
];

const DETECTIONS = [
  { id: 1, category: "fire",    confidence: 0.97, drone: "ALPHA-01", time: "1m ago" },
  { id: 2, category: "person",  confidence: 0.89, drone: "BRAVO-01", time: "3m ago" },
  { id: 3, category: "vehicle", confidence: 0.93, drone: "BRAVO-02", time: "4m ago" },
  { id: 4, category: "flood",   confidence: 0.85, drone: "CHARLIE-01", time: "6m ago" },
  { id: 5, category: "damage",  confidence: 0.91, drone: "ALPHA-02", time: "8m ago" },
  { id: 6, category: "person",  confidence: 0.78, drone: "CHARLIE-02", time: "9m ago" },
];

const CATEGORY_COLORS = {
  fire:    "bg-fire-red/20 text-fire-red",
  flood:   "bg-water-blue/20 text-water-blue",
  damage:  "bg-amber-400/20 text-amber-400",
  person:  "bg-emerald-400/20 text-emerald-400",
  vehicle: "bg-violet-400/20 text-violet-400",
};

const STATUS_DOT = {
  flying:  "bg-emerald-400 shadow-emerald-400/50",
  standby: "bg-amber-400 shadow-amber-400/50",
  offline: "bg-slate-600",
};

const SEVERITY_BORDER = {
  critical: "border-l-fire-red",
  warning:  "border-l-amber-400",
  info:     "border-l-sky-400",
};

/* ---------- sub-components ---------- */
function StatCard({ label, value, icon: Icon, color, bg }) {
  return (
    <div className="flex items-center gap-4 rounded-xl bg-slate-900 border border-slate-800 px-5 py-4">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${bg}`}>
        <Icon className={`h-5 w-5 ${color}`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-100">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

/* ---------- main dashboard ---------- */
export default function Dashboard() {
  return (
    <div className="flex flex-col gap-4 p-4 h-screen overflow-hidden">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {STATS.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* Main body: map + right panels */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Map - 70 % */}
        <div className="w-[70%]">
          <DroneMap className="h-full" />
        </div>

        {/* Right panels - 30 % */}
        <div className="w-[30%] flex flex-col gap-4 overflow-hidden">

          {/* Active Alerts */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Active Alerts</h2>
              <span className="text-[10px] font-medium bg-fire-red/20 text-fire-red px-2 py-0.5 rounded-full">
                {ALERTS.length} active
              </span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-thin">
              {ALERTS.map((a) => (
                <div
                  key={a.id}
                  className={`flex items-start gap-3 rounded-lg bg-slate-800/50 border-l-2 px-3 py-2.5 ${SEVERITY_BORDER[a.severity]}`}
                >
                  <a.icon className={`h-4 w-4 mt-0.5 shrink-0 ${a.color}`} />
                  <div className="min-w-0">
                    <p className="text-xs text-slate-300 leading-snug">{a.text}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{a.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fleet Status */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Fleet Status</h2>
              <span className="text-[10px] text-slate-500">
                {FLEET.filter((d) => d.status === "flying").length}/{FLEET.length} active
              </span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {FLEET.map((d) => (
                <div key={d.callsign} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                  <span className={`h-2 w-2 rounded-full shadow-sm ${STATUS_DOT[d.status]}`} />
                  <span className="text-xs font-medium text-slate-300 w-24 shrink-0">{d.callsign}</span>
                  <div className="flex-1 min-w-0">
                    <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          d.battery > 50
                            ? "bg-emerald-500"
                            : d.battery > 25
                            ? "bg-amber-500"
                            : "bg-fire-red"
                        }`}
                        style={{ width: `${d.battery}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-500 w-8 text-right">{d.battery}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Detections */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Recent Detections</h2>
              <span className="text-[10px] text-slate-500">{DETECTIONS.length} latest</span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {DETECTIONS.map((d) => (
                <div key={d.id} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                  <span
                    className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded ${
                      CATEGORY_COLORS[d.category] ?? "bg-slate-600/30 text-slate-400"
                    }`}
                  >
                    {d.category}
                  </span>
                  <span className="text-xs text-slate-400 flex-1">{d.drone}</span>
                  <span className="text-[10px] text-slate-500">{(d.confidence * 100).toFixed(0)}%</span>
                  <span className="text-[10px] text-slate-600">{d.time}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

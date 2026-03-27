import React, { useState, useEffect, useCallback } from "react";
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
  Play,
  Square,
  Database,
} from "lucide-react";
import DroneMap from "../Map/DroneMap";
import {
  getIncidents,
  getDrones,
  getDetections,
  getActiveAlerts,
  seedDemo,
  startSimulator,
  stopSimulator,
  getSimulatorStatus,
} from "../../services/api";

/* ---------- placeholder / fallback data ---------- */
const FALLBACK_STATS = [
  { label: "Active Incidents", value: 3, icon: AlertTriangle, color: "text-fire-red", bg: "bg-fire-red/10" },
  { label: "Drones Flying", value: 7, icon: Plane, color: "text-sky-400", bg: "bg-sky-400/10" },
  { label: "Detections Today", value: 142, icon: ScanSearch, color: "text-amber-400", bg: "bg-amber-400/10" },
  { label: "Active Alerts", value: 5, icon: Bell, color: "text-rose-400", bg: "bg-rose-400/10" },
];

const FALLBACK_ALERTS = [
  { id: 1, severity: "critical", text: "Fire spread detected NE sector - Incident #1042", time: "2m ago", icon: Flame, color: "text-fire-red" },
  { id: 2, severity: "warning", text: "Drone ALPHA-03 battery below 25%", time: "5m ago", icon: BatteryMedium, color: "text-amber-400" },
  { id: 3, severity: "critical", text: "Flood water rising at Checkpoint Bravo", time: "8m ago", icon: Droplets, color: "text-water-blue" },
  { id: 4, severity: "info", text: "Structural damage confirmed at 42nd & Main", time: "12m ago", icon: Building2, color: "text-amber-400" },
  { id: 5, severity: "warning", text: "EMQX connection latency > 500ms", time: "15m ago", icon: Signal, color: "text-amber-400" },
];

const FALLBACK_FLEET = [
  { callsign: "ALPHA-01", status: "flying", battery: 82 },
  { callsign: "ALPHA-02", status: "flying", battery: 64 },
  { callsign: "ALPHA-03", status: "flying", battery: 23 },
  { callsign: "BRAVO-01", status: "flying", battery: 91 },
  { callsign: "BRAVO-02", status: "flying", battery: 77 },
  { callsign: "CHARLIE-01", status: "flying", battery: 55 },
  { callsign: "CHARLIE-02", status: "flying", battery: 48 },
  { callsign: "DELTA-01", status: "standby", battery: 100 },
  { callsign: "DELTA-02", status: "offline", battery: 0 },
];

const FALLBACK_DETECTIONS = [
  { id: 1, category: "fire", confidence: 0.97, drone: "ALPHA-01", time: "1m ago" },
  { id: 2, category: "person", confidence: 0.89, drone: "BRAVO-01", time: "3m ago" },
  { id: 3, category: "vehicle", confidence: 0.93, drone: "BRAVO-02", time: "4m ago" },
  { id: 4, category: "flood", confidence: 0.85, drone: "CHARLIE-01", time: "6m ago" },
  { id: 5, category: "damage", confidence: 0.91, drone: "ALPHA-02", time: "8m ago" },
  { id: 6, category: "person", confidence: 0.78, drone: "CHARLIE-02", time: "9m ago" },
];

/* ---------- style maps ---------- */
const CATEGORY_COLORS = {
  fire: "bg-fire-red/20 text-fire-red",
  flood: "bg-water-blue/20 text-water-blue",
  damage: "bg-amber-400/20 text-amber-400",
  person: "bg-emerald-400/20 text-emerald-400",
  vehicle: "bg-violet-400/20 text-violet-400",
};

const STATUS_DOT = {
  flying: "bg-emerald-400 shadow-emerald-400/50",
  online: "bg-emerald-400 shadow-emerald-400/50",
  standby: "bg-amber-400 shadow-amber-400/50",
  offline: "bg-slate-600",
};

const SEVERITY_BORDER = {
  critical: "border-l-fire-red",
  warning: "border-l-amber-400",
  info: "border-l-sky-400",
};

const SEVERITY_ICON = {
  critical: { icon: Flame, color: "text-fire-red" },
  warning: { icon: BatteryMedium, color: "text-amber-400" },
  info: { icon: Signal, color: "text-sky-400" },
};

/* ---------- helpers ---------- */
function relativeTime(dateString) {
  if (!dateString) return "";
  const now = new Date();
  const then = new Date(dateString);
  const diffMs = now - then;
  if (isNaN(diffMs)) return dateString;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

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
  const [stats, setStats] = useState(FALLBACK_STATS);
  const [alerts, setAlerts] = useState(FALLBACK_ALERTS);
  const [fleet, setFleet] = useState(FALLBACK_FLEET);
  const [detections, setDetections] = useState(FALLBACK_DETECTIONS);
  const [simRunning, setSimRunning] = useState(false);
  const [simLoading, setSimLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [incRes, droneRes, detRes, alertRes] = await Promise.allSettled([
        getIncidents(),
        getDrones(),
        getDetections(),
        getActiveAlerts(),
      ]);

      // --- Stats ---
      const incidents = incRes.status === "fulfilled" ? incRes.value.data : null;
      const drones = droneRes.status === "fulfilled" ? droneRes.value.data : null;
      const det = detRes.status === "fulfilled" ? detRes.value.data : null;
      const activeAlerts = alertRes.status === "fulfilled" ? alertRes.value.data : null;

      const incidentList = Array.isArray(incidents) ? incidents : incidents?.items ?? [];
      const droneList = Array.isArray(drones) ? drones : drones?.items ?? [];
      const detList = Array.isArray(det) ? det : det?.items ?? [];
      const alertList = Array.isArray(activeAlerts) ? activeAlerts : activeAlerts?.items ?? [];

      const activeIncidents = incidentList.filter((i) => i.status === "active").length || incidentList.length;
      const flyingDrones = droneList.filter((d) => d.status === "flying").length;

      if (incRes.status === "fulfilled" || droneRes.status === "fulfilled" || detRes.status === "fulfilled" || alertRes.status === "fulfilled") {
        setStats([
          { label: "Active Incidents", value: activeIncidents, icon: AlertTriangle, color: "text-fire-red", bg: "bg-fire-red/10" },
          { label: "Drones Flying", value: flyingDrones, icon: Plane, color: "text-sky-400", bg: "bg-sky-400/10" },
          { label: "Detections Today", value: detList.length, icon: ScanSearch, color: "text-amber-400", bg: "bg-amber-400/10" },
          { label: "Active Alerts", value: alertList.length, icon: Bell, color: "text-rose-400", bg: "bg-rose-400/10" },
        ]);
      }

      // --- Active Alerts panel ---
      if (alertRes.status === "fulfilled" && alertList.length > 0) {
        setAlerts(
          alertList.map((a) => {
            const sev = a.severity || "info";
            const iconConf = SEVERITY_ICON[sev] || SEVERITY_ICON.info;
            return {
              id: a.id,
              severity: sev,
              text: a.message || a.title || a.description || "Alert",
              time: relativeTime(a.created_at),
              icon: iconConf.icon,
              color: iconConf.color,
            };
          })
        );
      }

      // --- Fleet panel ---
      if (droneRes.status === "fulfilled" && droneList.length > 0) {
        setFleet(
          droneList.map((d) => ({
            callsign: d.name || d.callsign || d.serial_number || "Unknown",
            status: d.status || "offline",
            battery: d.battery ?? d.battery_level ?? 0,
          }))
        );
      }

      // --- Detections panel ---
      if (detRes.status === "fulfilled" && detList.length > 0) {
        setDetections(
          detList.slice(0, 10).map((d) => ({
            id: d.id,
            category: d.category || d.type || "unknown",
            confidence: d.confidence ?? 0,
            drone: d.drone_id || d.drone_serial || d.drone || "\u2014",
            time: relativeTime(d.created_at || d.detected_at),
          }))
        );
      }
    } catch {
      // keep fallback data on total failure
    }
  }, []);

  const fetchSimStatus = useCallback(async () => {
    try {
      const res = await getSimulatorStatus();
      setSimRunning(res.data?.running ?? res.data?.status === "running");
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchSimStatus();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData, fetchSimStatus]);

  const handleSeed = async () => {
    setSimLoading(true);
    try {
      await seedDemo();
      await fetchData();
    } catch {
      // ignore
    }
    setSimLoading(false);
  };

  const handleToggleSim = async () => {
    setSimLoading(true);
    try {
      if (simRunning) {
        await stopSimulator();
        setSimRunning(false);
      } else {
        await startSimulator();
        setSimRunning(true);
      }
    } catch {
      // ignore
    }
    setSimLoading(false);
  };

  return (
    <div className="flex flex-col gap-4 p-4 h-screen overflow-hidden">
      {/* Demo Controls */}
      <div className="flex items-center gap-3 rounded-xl bg-slate-900 border border-slate-800 px-4 py-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-2">Demo Controls</span>
        <button
          onClick={handleSeed}
          disabled={simLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-400 border border-violet-500/30 hover:bg-violet-500/25 transition-colors disabled:opacity-50"
        >
          <Database className="h-3.5 w-3.5" />
          Seed Data
        </button>
        <button
          onClick={handleToggleSim}
          disabled={simLoading}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors disabled:opacity-50 ${
            simRunning
              ? "bg-fire-red/15 text-fire-red border-fire-red/30 hover:bg-fire-red/25"
              : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25"
          }`}
        >
          {simRunning ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          {simRunning ? "Stop Simulation" : "Start Simulation"}
        </button>
        {simRunning && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Simulation active
          </span>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((s) => (
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
                {alerts.length} active
              </span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-thin">
              {alerts.map((a) => (
                <div
                  key={a.id}
                  className={`flex items-start gap-3 rounded-lg bg-slate-800/50 border-l-2 px-3 py-2.5 ${SEVERITY_BORDER[a.severity] || "border-l-sky-400"}`}
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
                {fleet.filter((d) => d.status === "flying").length}/{fleet.length} active
              </span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {fleet.map((d) => (
                <div key={d.callsign} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                  <span className={`h-2 w-2 rounded-full shadow-sm ${STATUS_DOT[d.status] || "bg-slate-600"}`} />
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
              <span className="text-[10px] text-slate-500">{detections.length} latest</span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {detections.map((d) => (
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

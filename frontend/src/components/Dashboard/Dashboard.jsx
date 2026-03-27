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

const CATEGORY_COLORS = {
  fire: "bg-fire-red/20 text-fire-red",
  smoke: "bg-amber-400/20 text-amber-400",
  flood_water: "bg-water-blue/20 text-water-blue",
  structural_damage: "bg-amber-400/20 text-amber-400",
  person: "bg-emerald-400/20 text-emerald-400",
  vehicle: "bg-violet-400/20 text-violet-400",
  hazmat: "bg-purple-400/20 text-purple-400",
};

const STATUS_DOT = {
  flying: "bg-emerald-400 shadow-emerald-400/50",
  online: "bg-emerald-400 shadow-emerald-400/50",
  charging: "bg-blue-400 shadow-blue-400/50",
  returning: "bg-purple-400 shadow-purple-400/50",
  offline: "bg-slate-600",
};

const SEVERITY_BORDER = {
  critical: "border-l-fire-red",
  high: "border-l-amber-400",
  medium: "border-l-sky-400",
  low: "border-l-slate-500",
};

function relativeTime(dateString) {
  if (!dateString) return "";
  const diffMs = Date.now() - new Date(dateString).getTime();
  if (isNaN(diffMs)) return "";
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return s + "s ago";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m ago";
  const h = Math.floor(m / 60);
  return h + "h ago";
}

function StatCard({ label, value, icon: Icon, color, bg }) {
  return (
    <div className="flex items-center gap-4 rounded-xl bg-slate-900 border border-slate-800 px-5 py-4">
      <div className={"flex h-11 w-11 shrink-0 items-center justify-center rounded-lg " + bg}>
        <Icon className={"h-5 w-5 " + color} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-100">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [incidents, setIncidents] = useState([]);
  const [drones, setDrones] = useState([]);
  const [detections, setDetections] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [simRunning, setSimRunning] = useState(false);
  const [simLoading, setSimLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [incRes, droneRes, detRes, alertRes] = await Promise.allSettled([
        getIncidents(), getDrones(), getDetections(), getActiveAlerts(),
      ]);
      if (incRes.status === "fulfilled") setIncidents(incRes.value.data || []);
      if (droneRes.status === "fulfilled") setDrones(droneRes.value.data || []);
      if (detRes.status === "fulfilled") setDetections(detRes.value.data || []);
      if (alertRes.status === "fulfilled") setAlerts(alertRes.value.data || []);
    } catch { /* keep existing data */ }
  }, []);

  useEffect(() => {
    fetchData();
    getSimulatorStatus().then(r => setSimRunning(r.data?.running)).catch(() => {});
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleSeed = async () => {
    setSimLoading(true);
    try { await seedDemo(); await fetchData(); } catch {}
    setSimLoading(false);
  };

  const handleToggleSim = async () => {
    setSimLoading(true);
    try {
      if (simRunning) { await stopSimulator(); setSimRunning(false); }
      else { await startSimulator(); setSimRunning(true); }
    } catch {}
    setSimLoading(false);
  };

  const activeIncidents = incidents.filter(i => i.status === "active").length;
  const flyingDrones = drones.filter(d => d.status === "flying").length;

  return (
    <div className="flex flex-col gap-4 p-4 h-screen overflow-hidden">
      {/* Demo Controls */}
      <div className="flex items-center gap-3 rounded-xl bg-slate-900 border border-slate-800 px-4 py-2">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-2">Demo</span>
        <button onClick={handleSeed} disabled={simLoading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-400 border border-violet-500/30 hover:bg-violet-500/25 transition-colors disabled:opacity-50">
          <Database className="h-3.5 w-3.5" /> Seed Data
        </button>
        <button onClick={handleToggleSim} disabled={simLoading}
          className={"inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors disabled:opacity-50 " +
            (simRunning ? "bg-fire-red/15 text-fire-red border-fire-red/30 hover:bg-fire-red/25" : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25")}>
          {simRunning ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          {simRunning ? "Stop Simulation" : "Start Simulation"}
        </button>
        {simRunning && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> Simulation active
          </span>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Active Incidents" value={activeIncidents || incidents.length} icon={AlertTriangle} color="text-fire-red" bg="bg-fire-red/10" />
        <StatCard label="Drones Flying" value={flyingDrones} icon={Plane} color="text-sky-400" bg="bg-sky-400/10" />
        <StatCard label="Detections" value={detections.length} icon={ScanSearch} color="text-amber-400" bg="bg-amber-400/10" />
        <StatCard label="Active Alerts" value={alerts.length} icon={Bell} color="text-rose-400" bg="bg-rose-400/10" />
      </div>

      {/* Map + Panels */}
      <div className="flex gap-4 flex-1 min-h-0">
        <div className="w-[70%]"><DroneMap className="h-full" /></div>
        <div className="w-[30%] flex flex-col gap-4 overflow-hidden">

          {/* Alerts */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Active Alerts</h2>
              <span className="text-[10px] font-medium bg-fire-red/20 text-fire-red px-2 py-0.5 rounded-full">{alerts.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-thin">
              {alerts.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No active alerts</p>}
              {alerts.map(a => (
                <div key={a.id} className={"flex items-start gap-3 rounded-lg bg-slate-800/50 border-l-2 px-3 py-2.5 " + (SEVERITY_BORDER[a.severity] || "border-l-sky-400")}>
                  <Flame className={"h-4 w-4 mt-0.5 shrink-0 " + (a.severity === "critical" ? "text-fire-red" : "text-amber-400")} />
                  <div className="min-w-0">
                    <p className="text-xs text-slate-300 leading-snug">{a.message}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5">{relativeTime(a.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fleet */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Fleet Status</h2>
              <span className="text-[10px] text-slate-500">{flyingDrones}/{drones.length} active</span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {drones.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No drones registered</p>}
              {drones.map(d => (
                <div key={d.id} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                  <span className={"h-2 w-2 rounded-full shadow-sm " + (STATUS_DOT[d.status] || "bg-slate-600")} />
                  <span className="text-xs font-medium text-slate-300 w-24 shrink-0">{d.name}</span>
                  <div className="flex-1 min-w-0">
                    <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div className={"h-full rounded-full transition-all bg-emerald-500"} style={{ width: "75%" }} />
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-500 w-16 text-right">{d.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Detections */}
          <div className="flex-1 min-h-0 rounded-xl bg-slate-900 border border-slate-800 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">Recent Detections</h2>
              <span className="text-[10px] text-slate-500">{detections.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5 scrollbar-thin">
              {detections.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No detections yet</p>}
              {detections.slice(0, 10).map(d => (
                <div key={d.id} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
                  <span className={"text-[10px] font-semibold uppercase px-2 py-0.5 rounded " + (CATEGORY_COLORS[d.category] || "bg-slate-600/30 text-slate-400")}>
                    {d.category}
                  </span>
                  <span className="text-xs text-slate-400 flex-1">Drone #{d.drone_id}</span>
                  <span className="text-[10px] text-slate-500">{(d.confidence * 100).toFixed(0)}%</span>
                  <span className="text-[10px] text-slate-600">{relativeTime(d.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

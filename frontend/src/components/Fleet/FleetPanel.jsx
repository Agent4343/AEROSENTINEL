import React, { useState } from "react";
import {
  Plane,
  BatteryFull,
  BatteryMedium,
  BatteryLow,
  BatteryWarning,
  Signal,
  SignalZero,
  MapPin,
  Clock,
} from "lucide-react";

/* ---------- placeholder fleet data ---------- */
const DRONES = [
  {
    id: "drone-001",
    callsign: "ALPHA-01",
    model: "DJI Matrice 350 RTK",
    status: "flying",
    battery: 82,
    altitude: 120,
    speed: 12.4,
    lat: 34.0522,
    lng: -118.2437,
    mission: "Incident #1042 - Wildfire Recon",
    flightTime: "01:22:15",
    signalStrength: 95,
    lastUpdate: "2s ago",
  },
  {
    id: "drone-002",
    callsign: "ALPHA-02",
    model: "DJI Matrice 350 RTK",
    status: "flying",
    battery: 64,
    altitude: 95,
    speed: 8.7,
    lat: 34.0548,
    lng: -118.2401,
    mission: "Incident #1042 - Thermal Mapping",
    flightTime: "00:58:33",
    signalStrength: 88,
    lastUpdate: "1s ago",
  },
  {
    id: "drone-003",
    callsign: "ALPHA-03",
    model: "DJI Mavic 3 Enterprise",
    status: "flying",
    battery: 23,
    altitude: 80,
    speed: 5.2,
    lat: 34.0510,
    lng: -118.2450,
    mission: "Incident #1042 - Perimeter Watch",
    flightTime: "01:45:08",
    signalStrength: 72,
    lastUpdate: "3s ago",
  },
  {
    id: "drone-004",
    callsign: "BRAVO-01",
    model: "DJI Matrice 350 RTK",
    status: "flying",
    battery: 91,
    altitude: 150,
    speed: 14.1,
    lat: 29.7604,
    lng: -95.3698,
    mission: "Incident #1038 - Flood Assessment",
    flightTime: "00:32:41",
    signalStrength: 97,
    lastUpdate: "1s ago",
  },
  {
    id: "drone-005",
    callsign: "BRAVO-02",
    model: "DJI Matrice 30T",
    status: "flying",
    battery: 77,
    altitude: 110,
    speed: 10.0,
    lat: 29.7620,
    lng: -95.3670,
    mission: "Incident #1038 - Search & Rescue",
    flightTime: "00:48:12",
    signalStrength: 91,
    lastUpdate: "2s ago",
  },
  {
    id: "drone-006",
    callsign: "CHARLIE-01",
    model: "DJI Mavic 3 Enterprise",
    status: "flying",
    battery: 55,
    altitude: 60,
    speed: 7.3,
    lat: 40.7128,
    lng: -74.006,
    mission: "Patrol Zone C - Routine",
    flightTime: "01:10:55",
    signalStrength: 84,
    lastUpdate: "1s ago",
  },
  {
    id: "drone-007",
    callsign: "CHARLIE-02",
    model: "DJI Mavic 3 Enterprise",
    status: "flying",
    battery: 48,
    altitude: 65,
    speed: 6.1,
    lat: 40.7145,
    lng: -74.003,
    mission: "Patrol Zone C - Routine",
    flightTime: "01:15:20",
    signalStrength: 79,
    lastUpdate: "4s ago",
  },
  {
    id: "drone-008",
    callsign: "DELTA-01",
    model: "DJI Matrice 350 RTK",
    status: "standby",
    battery: 100,
    altitude: 0,
    speed: 0,
    lat: 37.7749,
    lng: -122.4194,
    mission: "Unassigned",
    flightTime: "\u2014",
    signalStrength: 100,
    lastUpdate: "10s ago",
  },
  {
    id: "drone-009",
    callsign: "DELTA-02",
    model: "DJI Matrice 30T",
    status: "offline",
    battery: 0,
    altitude: 0,
    speed: 0,
    lat: 37.775,
    lng: -122.418,
    mission: "Maintenance",
    flightTime: "\u2014",
    signalStrength: 0,
    lastUpdate: "2h ago",
  },
];

/* ---------- helpers ---------- */
const STATUS_CONFIG = {
  flying:  { label: "Flying",  dot: "bg-emerald-400 shadow-emerald-400/50", badge: "bg-emerald-400/15 text-emerald-400" },
  standby: { label: "Standby", dot: "bg-amber-400 shadow-amber-400/50",    badge: "bg-amber-400/15 text-amber-400" },
  offline: { label: "Offline", dot: "bg-slate-600",                         badge: "bg-slate-600/15 text-slate-500" },
};

function BatteryIcon({ level }) {
  if (level > 75) return <BatteryFull className="h-4 w-4 text-emerald-400" />;
  if (level > 50) return <BatteryMedium className="h-4 w-4 text-emerald-400" />;
  if (level > 25) return <BatteryLow className="h-4 w-4 text-amber-400" />;
  return <BatteryWarning className="h-4 w-4 text-fire-red" />;
}

function batteryColor(level) {
  if (level > 50) return "bg-emerald-500";
  if (level > 25) return "bg-amber-500";
  return "bg-fire-red";
}

/* ---------- component ---------- */
export default function FleetPanel() {
  const [filter, setFilter] = useState("all");

  const filtered =
    filter === "all" ? DRONES : DRONES.filter((d) => d.status === filter);

  const counts = {
    all: DRONES.length,
    flying: DRONES.filter((d) => d.status === "flying").length,
    standby: DRONES.filter((d) => d.status === "standby").length,
    offline: DRONES.filter((d) => d.status === "offline").length,
  };

  return (
    <div className="p-6 space-y-6 h-screen overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Fleet Management</h1>
        <p className="text-sm text-slate-500 mt-1">
          Monitor and control all registered drones across active deployments.
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(["all", "flying", "standby", "offline"]).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-2 rounded-lg text-xs font-medium capitalize transition-colors ${
              filter === key
                ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
            }`}
          >
            {key} ({counts[key]})
          </button>
        ))}
      </div>

      {/* Drone cards */}
      <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4">
        {filtered.map((drone) => {
          const sc = STATUS_CONFIG[drone.status];
          return (
            <div
              key={drone.id}
              className="rounded-xl bg-slate-900 border border-slate-800 p-4 space-y-4 hover:border-slate-700 transition-colors"
            >
              {/* Top row: callsign + status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/10">
                    <Plane className="h-4.5 w-4.5 text-sky-400" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-100">{drone.callsign}</p>
                    <p className="text-[10px] text-slate-500">{drone.model}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold px-2.5 py-1 rounded-full ${sc.badge}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${sc.dot}`} />
                  {sc.label}
                </span>
              </div>

              {/* Battery bar */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <BatteryIcon level={drone.battery} />
                    <span className="text-xs text-slate-300">{drone.battery}%</span>
                  </div>
                  {drone.status === "flying" && (
                    <div className="flex items-center gap-1 text-[10px] text-slate-500">
                      <Clock className="h-3 w-3" />
                      {drone.flightTime}
                    </div>
                  )}
                </div>
                <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${batteryColor(drone.battery)}`}
                    style={{ width: `${drone.battery}%` }}
                  />
                </div>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="text-[10px] text-slate-600 uppercase">Altitude</p>
                  <p className="text-xs font-medium text-slate-300">{drone.altitude}m</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-600 uppercase">Speed</p>
                  <p className="text-xs font-medium text-slate-300">{drone.speed} m/s</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-600 uppercase">Signal</p>
                  <div className="flex items-center gap-1">
                    {drone.signalStrength > 0 ? (
                      <Signal className="h-3 w-3 text-emerald-400" />
                    ) : (
                      <SignalZero className="h-3 w-3 text-slate-600" />
                    )}
                    <span className="text-xs font-medium text-slate-300">{drone.signalStrength}%</span>
                  </div>
                </div>
              </div>

              {/* Mission assignment */}
              <div className="flex items-start gap-2 rounded-lg bg-slate-800/50 px-3 py-2">
                <MapPin className="h-3.5 w-3.5 mt-0.5 text-slate-500 shrink-0" />
                <div className="min-w-0">
                  <p className="text-[10px] text-slate-600 uppercase">Current Mission</p>
                  <p className="text-xs text-slate-300 truncate">{drone.mission}</p>
                </div>
              </div>

              {/* Footer */}
              <p className="text-[10px] text-slate-600 text-right">
                Last telemetry: {drone.lastUpdate}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

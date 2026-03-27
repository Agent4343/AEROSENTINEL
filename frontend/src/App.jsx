import React from "react";
import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import {
  LayoutDashboard,
  AlertTriangle,
  Navigation,
  Radio,
  Bell,
  Shield,
} from "lucide-react";
import Dashboard from "./components/Dashboard/Dashboard";
import FleetPanel from "./components/Fleet/FleetPanel";
import clsx from "clsx";

/* ---- Placeholder pages ---- */
const Incidents = () => (
  <div className="p-8">
    <h1 className="text-2xl font-bold text-slate-100 mb-4">Incident Management</h1>
    <p className="text-slate-400">Active and historical incident tracking will appear here.</p>
  </div>
);

const Missions = () => (
  <div className="p-8">
    <h1 className="text-2xl font-bold text-slate-100 mb-4">Mission Planning</h1>
    <p className="text-slate-400">Wayline planning and mission orchestration will appear here.</p>
  </div>
);

const Alerts = () => (
  <div className="p-8">
    <h1 className="text-2xl font-bold text-slate-100 mb-4">Alert Center</h1>
    <p className="text-slate-400">Real-time alerts and notification history will appear here.</p>
  </div>
);

/* ---- Sidebar navigation items ---- */
const NAV_ITEMS = [
  { to: "/",          icon: LayoutDashboard, label: "Dashboard" },
  { to: "/incidents",  icon: AlertTriangle,   label: "Incidents" },
  { to: "/missions",   icon: Navigation,      label: "Missions" },
  { to: "/fleet",      icon: Radio,           label: "Fleet" },
  { to: "/alerts",     icon: Bell,            label: "Alerts" },
];

function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-900 border-r border-slate-800">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-800">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10">
          <Shield className="h-5 w-5 text-amber-400" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-slate-100">
            AeroSentinel
          </h1>
          <p className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
            Emergency Response
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-amber-500/10 text-amber-400"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              )
            }
          >
            <Icon className="h-4.5 w-4.5 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-800 px-5 py-3">
        <p className="text-[10px] text-slate-600">
          AeroSentinel v1.0 &middot; System Operational
        </p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950">
      <Sidebar />
      <main className="pl-64 min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/missions" element={<Missions />} />
          <Route path="/fleet" element={<FleetPanel />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

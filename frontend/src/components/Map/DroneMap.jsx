import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import { getDrones, getDetections, getIncidents } from "../../services/api";

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const API_BASE = process.env.REACT_APP_API_BASE_URL || "";

const DETECTION_COLORS = {
  fire: "#ef4444",
  smoke: "#f97316",
  flood_water: "#3b82f6",
  structural_damage: "#f59e0b",
  person: "#22c55e",
  vehicle: "#8b5cf6",
  hazmat: "#a855f7",
};

const INCIDENT_COLORS = {
  wildfire: "#ef4444",
  flood: "#3b82f6",
  structural: "#f59e0b",
  earthquake: "#f97316",
  hazmat: "#a855f7",
  search_rescue: "#22c55e",
};

const DRONE_COLOR = "#38bdf8";

function createCirclePolygon(lat, lon, radiusM, points = 64) {
  const coords = [];
  const rDeg = radiusM / 111320;
  for (let i = 0; i <= points; i++) {
    const angle = (i / points) * 2 * Math.PI;
    coords.push([
      lon + rDeg * Math.cos(angle) / Math.cos(lat * Math.PI / 180),
      lat + rDeg * Math.sin(angle),
    ]);
  }
  return coords;
}

export default function DroneMap({ className = "" }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(null);
  const hasFitted = useRef(false);

  useEffect(() => {
    if (map.current) return;
    try {
      map.current = new maplibregl.Map({
        container: mapContainer.current,
        style: MAP_STYLE,
        center: [-98.5, 39.8],
        zoom: 4,
        attributionControl: false,
      });
      map.current.addControl(new maplibregl.NavigationControl(), "top-right");

      map.current.on("load", () => {
        // Drone positions
        map.current.addSource("drones", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "drone-glow", type: "circle", source: "drones", paint: { "circle-radius": 14, "circle-color": DRONE_COLOR, "circle-opacity": 0.15, "circle-blur": 1 } });
        map.current.addLayer({ id: "drone-icons", type: "circle", source: "drones", paint: { "circle-radius": 6, "circle-color": DRONE_COLOR, "circle-stroke-width": 2, "circle-stroke-color": "#0f172a" } });
        map.current.addLayer({ id: "drone-labels", type: "symbol", source: "drones", layout: { "text-field": ["get", "name"], "text-size": 10, "text-offset": [0, 1.6], "text-anchor": "top", "text-allow-overlap": true }, paint: { "text-color": "#e2e8f0", "text-halo-color": "#0f172a", "text-halo-width": 1 } });

        // Incident areas
        map.current.addSource("incidents", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "incident-fill", type: "fill", source: "incidents", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.1 } });
        map.current.addLayer({ id: "incident-border", type: "line", source: "incidents", paint: { "line-color": ["get", "color"], "line-width": 2, "line-dasharray": [3, 2] } });
        map.current.addLayer({ id: "incident-labels", type: "symbol", source: "incidents", layout: { "text-field": ["get", "title"], "text-size": 11, "text-anchor": "center", "text-allow-overlap": false }, paint: { "text-color": "#fbbf24", "text-halo-color": "#0f172a", "text-halo-width": 1.5 } });

        // Detection markers
        map.current.addSource("detections", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "detection-points", type: "circle", source: "detections", paint: { "circle-radius": 4, "circle-color": ["get", "color"], "circle-stroke-width": 1, "circle-stroke-color": "#0f172a", "circle-opacity": 0.85 } });

        // Popups
        map.current.on("click", "drone-icons", (e) => {
          const p = e.features[0].properties;
          new maplibregl.Popup({ closeButton: false, offset: 10 })
            .setLngLat(e.lngLat)
            .setHTML(`<div style="color:#e2e8f0;font-size:11px;line-height:1.4"><strong>${p.name}</strong><br/>${p.model || ""}<br/>Alt: ${p.altitude || "—"}m · Bat: ${p.battery || "—"}% · ${p.status}</div>`)
            .addTo(map.current);
        });

        map.current.on("click", "detection-points", (e) => {
          const p = e.features[0].properties;
          new maplibregl.Popup({ closeButton: false, offset: 10 })
            .setLngLat(e.lngLat)
            .setHTML(`<div style="color:#e2e8f0;font-size:11px;line-height:1.4"><strong>${(p.category || "").replace("_", " ")}</strong><br/>Confidence: ${p.confidence}%<br/>Severity: ${p.severity}</div>`)
            .addTo(map.current);
        });

        map.current.on("mouseenter", "drone-icons", () => { map.current.getCanvas().style.cursor = "pointer"; });
        map.current.on("mouseleave", "drone-icons", () => { map.current.getCanvas().style.cursor = ""; });
        map.current.on("mouseenter", "detection-points", () => { map.current.getCanvas().style.cursor = "pointer"; });
        map.current.on("mouseleave", "detection-points", () => { map.current.getCanvas().style.cursor = ""; });

        setMapReady(true);
      });

      map.current.on("error", (e) => console.warn("Map error:", e));
    } catch (err) {
      setMapError(err.message);
    }

    return () => { map.current?.remove(); map.current = null; };
  }, []);

  // Poll API every 2 seconds and update map layers
  const fetchAndUpdate = useCallback(async () => {
    if (!map.current || !mapReady) return;

    try {
      const [droneRes, detRes, incRes] = await Promise.allSettled([
        getDrones(), getDetections(), getIncidents(),
      ]);

      // Update drone positions
      if (droneRes.status === "fulfilled") {
        const droneList = droneRes.value.data || [];
        const droneFeatures = [];

        for (const d of droneList) {
          if (d.status === "offline") continue;
          // Fetch latest telemetry for each drone
          let lat = null, lon = null, alt = null, battery = null;
          try {
            const telRes = await fetch(`${API_BASE}/api/v1/drones/${d.serial_number}`);
            if (telRes.ok) {
              const detail = await telRes.json();
              const t = detail.latest_telemetry;
              if (t) { lat = t.latitude; lon = t.longitude; alt = t.altitude; battery = t.battery_percent; }
            }
          } catch { /* skip */ }

          if (lat != null && lon != null) {
            droneFeatures.push({
              type: "Feature",
              geometry: { type: "Point", coordinates: [lon, lat] },
              properties: { name: d.name, model: d.model, status: d.status, altitude: alt ? Math.round(alt) : "—", battery: battery ? Math.round(battery) : "—" },
            });
          }
        }

        if (map.current.getSource("drones")) {
          map.current.getSource("drones").setData({ type: "FeatureCollection", features: droneFeatures });
        }

        // Auto-fit map to drone positions on first data load
        if (!hasFitted.current && droneFeatures.length > 0) {
          hasFitted.current = true;
          const bounds = new maplibregl.LngLatBounds();
          droneFeatures.forEach(f => bounds.extend(f.geometry.coordinates));
          map.current.fitBounds(bounds, { padding: 80, maxZoom: 12, duration: 1500 });
        }
      }

      // Update detection markers
      if (detRes.status === "fulfilled") {
        const detList = detRes.value.data || [];
        const detFeatures = detList.map(d => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [d.longitude, d.latitude] },
          properties: { category: d.category, color: DETECTION_COLORS[d.category] || "#94a3b8", confidence: Math.round(d.confidence * 100), severity: d.severity },
        }));

        if (map.current.getSource("detections")) {
          map.current.getSource("detections").setData({ type: "FeatureCollection", features: detFeatures });
        }
      }

      // Update incident zones
      if (incRes.status === "fulfilled") {
        const incList = incRes.value.data || [];
        const incFeatures = incList.map(inc => ({
          type: "Feature",
          geometry: { type: "Polygon", coordinates: [createCirclePolygon(inc.latitude, inc.longitude, inc.radius_meters)] },
          properties: { title: inc.title, color: INCIDENT_COLORS[inc.type] || "#f59e0b" },
        }));

        if (map.current.getSource("incidents")) {
          map.current.getSource("incidents").setData({ type: "FeatureCollection", features: incFeatures });
        }
      }
    } catch { /* ignore */ }
  }, [mapReady]);

  useEffect(() => {
    if (!mapReady) return;
    fetchAndUpdate();
    const interval = setInterval(fetchAndUpdate, 2000);
    return () => clearInterval(interval);
  }, [mapReady, fetchAndUpdate]);

  if (mapError) {
    return (
      <div className={`flex items-center justify-center rounded-lg border border-slate-800 bg-slate-900 ${className}`} style={{ minHeight: 500 }}>
        <p className="text-sm text-slate-500">Map failed to load: {mapError}</p>
      </div>
    );
  }

  return (
    <div className={`relative rounded-lg overflow-hidden border border-slate-800 ${className}`}>
      <div ref={mapContainer} className="w-full h-full min-h-[500px]" />
      <div className="absolute bottom-3 left-3 bg-slate-900/90 backdrop-blur rounded-lg px-3 py-2 text-[10px] space-y-1 border border-slate-700">
        <p className="font-semibold text-slate-300 uppercase tracking-wider mb-1">Legend</p>
        {Object.entries(DETECTION_COLORS).map(([key, color]) => (
          <div key={key} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="capitalize text-slate-400">{key.replace("_", " ")}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 border-t border-slate-700 mt-1">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: DRONE_COLOR }} />
          <span className="text-slate-400">Drone</span>
        </div>
      </div>
    </div>
  );
}

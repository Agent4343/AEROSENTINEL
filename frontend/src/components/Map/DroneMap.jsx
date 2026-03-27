import React, { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";

const WS_BASE = process.env.REACT_APP_WS_BASE_URL || "ws://localhost:8000";

// Free dark map style (no token required)
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const DETECTION_COLORS = {
  fire: "#ef4444",
  flood: "#3b82f6",
  damage: "#f59e0b",
  person: "#22c55e",
  vehicle: "#8b5cf6",
  default: "#94a3b8",
};

const DRONE_COLOR = "#38bdf8";

export default function DroneMap({ className = "" }) {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const wsRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapError, setMapError] = useState(null);

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
        map.current.addLayer({ id: "drone-icons", type: "circle", source: "drones", paint: { "circle-radius": 7, "circle-color": DRONE_COLOR, "circle-stroke-width": 2, "circle-stroke-color": "#0f172a" } });
        map.current.addLayer({ id: "drone-labels", type: "symbol", source: "drones", layout: { "text-field": ["get", "callsign"], "text-size": 11, "text-offset": [0, 1.4], "text-anchor": "top" }, paint: { "text-color": "#e2e8f0", "text-halo-color": "#0f172a", "text-halo-width": 1 } });

        // Incident areas
        map.current.addSource("incidents", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "incident-fill", type: "fill", source: "incidents", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.15 } });
        map.current.addLayer({ id: "incident-border", type: "line", source: "incidents", paint: { "line-color": ["get", "color"], "line-width": 2, "line-dasharray": [2, 2] } });

        // Detection markers
        map.current.addSource("detections", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "detection-points", type: "circle", source: "detections", paint: { "circle-radius": 5, "circle-color": ["get", "color"], "circle-stroke-width": 1, "circle-stroke-color": "#0f172a" } });

        // Mission waylines
        map.current.addSource("waylines", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "wayline-paths", type: "line", source: "waylines", paint: { "line-color": "#a78bfa", "line-width": 2, "line-opacity": 0.7 } });

        // Fire heatmap
        map.current.addSource("fire-heat", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "fire-heatmap", type: "heatmap", source: "fire-heat", paint: { "heatmap-weight": ["get", "intensity"], "heatmap-intensity": 1, "heatmap-radius": 30, "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(0,0,0,0)", 0.4, "rgba(253,141,60,0.6)", 0.8, "rgba(227,26,28,0.8)", 1, "rgba(177,0,38,0.9)"], "heatmap-opacity": 0.6 } });

        // Flood heatmap
        map.current.addSource("flood-heat", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.current.addLayer({ id: "flood-heatmap", type: "heatmap", source: "flood-heat", paint: { "heatmap-weight": ["get", "intensity"], "heatmap-intensity": 1, "heatmap-radius": 30, "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(0,0,0,0)", 0.4, "rgba(107,174,214,0.5)", 0.8, "rgba(33,113,181,0.7)", 1, "rgba(8,69,148,0.85)"], "heatmap-opacity": 0.6 } });

        // Popup on drone click
        map.current.on("click", "drone-icons", (e) => {
          const props = e.features[0].properties;
          new maplibregl.Popup({ closeButton: false })
            .setLngLat(e.lngLat)
            .setHTML(`<div class="text-xs"><strong>${props.callsign}</strong><br/>Alt: ${props.altitude ?? "\u2014"}m \u00b7 Bat: ${props.battery ?? "\u2014"}%</div>`)
            .addTo(map.current);
        });

        setMapReady(true);
      });

      map.current.on("error", (e) => {
        console.warn("Map error:", e);
      });
    } catch (err) {
      console.error("Failed to initialize map:", err);
      setMapError(err.message);
    }

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  const handleWsMessage = useCallback((event) => {
    if (!map.current || !mapReady) return;
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "drone_positions" && map.current.getSource("drones")) {
        map.current.getSource("drones").setData({ type: "FeatureCollection", features: (msg.payload || []).map((d) => ({ type: "Feature", geometry: { type: "Point", coordinates: [d.lng, d.lat] }, properties: { callsign: d.callsign, altitude: d.altitude, battery: d.battery } })) });
      }
      if (msg.type === "detections" && map.current.getSource("detections")) {
        map.current.getSource("detections").setData({ type: "FeatureCollection", features: (msg.payload || []).map((d) => ({ type: "Feature", geometry: { type: "Point", coordinates: [d.lng, d.lat] }, properties: { color: DETECTION_COLORS[d.category] || DETECTION_COLORS.default } })) });
      }
      if (msg.type === "incidents" && map.current.getSource("incidents")) map.current.getSource("incidents").setData(msg.payload);
      if (msg.type === "waylines" && map.current.getSource("waylines")) map.current.getSource("waylines").setData(msg.payload);
      if (msg.type === "fire_heat" && map.current.getSource("fire-heat")) map.current.getSource("fire-heat").setData(msg.payload);
      if (msg.type === "flood_heat" && map.current.getSource("flood-heat")) map.current.getSource("flood-heat").setData(msg.payload);
    } catch { /* ignore */ }
  }, [mapReady]);

  useEffect(() => {
    if (!mapReady) return;
    let reconnectTimer;
    const connect = () => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/map`);
        wsRef.current = ws;
        ws.addEventListener("message", handleWsMessage);
        ws.addEventListener("close", () => { reconnectTimer = setTimeout(connect, 3000); });
        ws.addEventListener("error", () => ws.close());
      } catch { /* ignore ws errors */ }
    };
    connect();
    return () => { clearTimeout(reconnectTimer); wsRef.current?.close(); };
  }, [mapReady, handleWsMessage]);

  if (mapError) {
    return (
      <div className={`flex items-center justify-center rounded-lg border border-slate-800 bg-slate-900 ${className}`} style={{ minHeight: 500 }}>
        <div className="text-center text-slate-500">
          <p className="text-sm">Map failed to load</p>
          <p className="text-xs mt-1">{mapError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative rounded-lg overflow-hidden border border-slate-800 ${className}`}>
      <div ref={mapContainer} className="w-full h-full min-h-[500px]" />
      <div className="absolute bottom-3 left-3 bg-slate-900/90 backdrop-blur rounded-lg px-3 py-2 text-[10px] space-y-1 border border-slate-700">
        <p className="font-semibold text-slate-300 uppercase tracking-wider mb-1">Legend</p>
        {Object.entries(DETECTION_COLORS).filter(([k]) => k !== "default").map(([key, color]) => (
          <div key={key} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="capitalize text-slate-400">{key}</span>
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

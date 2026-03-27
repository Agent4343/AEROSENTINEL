import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "";

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 10000,
});

export default api;

export const getIncidents = () => api.get("/incidents");
export const getDrones = () => api.get("/drones");
export const getMissions = () => api.get("/missions");
export const getDetections = () => api.get("/detections");
export const getDetectionStats = () => api.get("/detections/stats");
export const getAlerts = () => api.get("/alerts");
export const getActiveAlerts = () => api.get("/alerts/active");
export const acknowledgeAlert = (id) => api.post(`/alerts/${id}/acknowledge`);
export const seedDemo = () => api.post("/simulator/seed");
export const startSimulator = () => api.post("/simulator/start");
export const stopSimulator = () => api.post("/simulator/stop");
export const getSimulatorStatus = () => api.get("/simulator/status");

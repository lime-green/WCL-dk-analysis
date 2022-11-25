export const ANALYSIS_URL = {
  development: "http://localhost:8000/analyze_fight",
  production:
    "https://gcotfoo88f.execute-api.us-east-2.amazonaws.com/analyze_fight",
}[import.meta.env.MODE];

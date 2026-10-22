import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initThemeFromStorage } from "./theme/engine";
import "./index.css";

// Aplica o tema persistido antes do primeiro paint (evita flash).
initThemeFromStorage();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

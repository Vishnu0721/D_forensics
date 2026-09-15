import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { LabelModeProvider } from "./context/LabelMode";
import "./styles/app.css";

try {
  const stored = localStorage.getItem("df-theme");
  document.documentElement.setAttribute(
    "data-theme",
    stored === "dark" ? "dark" : "light",
  );
} catch {
  document.documentElement.setAttribute("data-theme", "light");
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <LabelModeProvider>
        <App />
      </LabelModeProvider>
    </BrowserRouter>
  </StrictMode>,
);

import { createRoot } from "react-dom/client";
import { ConnectedStudio } from "./ConnectedStudio";
import { Director } from "./Director";
import { App } from "./App";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/600.css";
import "./styles.css";
import "./director.css";
createRoot(document.getElementById("root")!).render(
  new URLSearchParams(location.search).get("mode") === "fixture" ? (
    <App />
  ) : location.hash.startsWith("#director") ? (
    <Director />
  ) : (
    <ConnectedStudio />
  ),
);

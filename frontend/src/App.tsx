import { useObservability } from "./hooks/useObservability";
import { Footer, Header, NavBar } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { MonitorPage } from "./pages/MonitorPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { RemediationPage } from "./pages/RemediationPage";
import { TimelinePage } from "./pages/TimelinePage";
import { GrafanaPage } from "./pages/GrafanaPage";
import type { TabId } from "./types";

function PageContent({ tab, obs }: { tab: TabId; obs: ReturnType<typeof useObservability> }) {
  switch (tab) {
    case "home":
      return <HomePage obs={obs} />;
    case "monitor":
      return <MonitorPage obs={obs} />;
    case "analysis":
      return <AnalysisPage obs={obs} />;
    case "incidents":
      return <IncidentsPage obs={obs} />;
    case "remediation":
      return <RemediationPage obs={obs} />;
    case "timeline":
      return <TimelinePage obs={obs} />;
    case "grafana":
      return <GrafanaPage />;
    default:
      return <HomePage obs={obs} />;
  }
}

export default function App() {
  const obs = useObservability();

  return (
    <div className="app-shell">
      <Header obs={obs} />
      <NavBar obs={obs} />
      <main className={`app-main ${obs.tab === "grafana" ? "app-main--wide" : ""}`} key={obs.tab}>
        <PageContent tab={obs.tab} obs={obs} />
      </main>
      <Footer />
    </div>
  );
}

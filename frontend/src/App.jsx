import "./App.scss";
import { Analysis } from "./Analysis.jsx";
import { LogAnalysisContextProvider } from "./LogAnalysisContext.jsx";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const twentyFourHoursInMs = 1000 * 60 * 60 * 24;
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnmount: false,
      refetchOnReconnect: false,
      retry: false,
      staleTime: twentyFourHoursInMs,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LogAnalysisContextProvider>
        <div className="App">
          <Analysis />
        </div>
      </LogAnalysisContextProvider>
    </QueryClientProvider>
  );
}

export default App;

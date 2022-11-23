import React, { createContext } from "react";
import { useQuery } from "@tanstack/react-query";

import { ANALYSIS_URL } from "./constants.js";

export const LogAnalysisContext = createContext(null);

const getURLParams = () => {
  const search = window.location.search;
  return new URLSearchParams(search);
};

export const LogAnalysisContextProvider = ({ children }) => {
  const urlParams = getURLParams();
  const source_id = urlParams.get("source");
  const fight_id = urlParams.get("fight");
  const report_id = urlParams.get("report");

  const { isLoading, error, data } = useQuery({
    queryKey: ["analyze", source_id, fight_id, report_id],
    queryFn: () => {
      if (!source_id || !fight_id || !report_id) {
        throw Error("Missing required parameters");
      }

      const url = `${ANALYSIS_URL}?${new URLSearchParams({
        source_id,
        fight_id,
        report_id,
      })}`;
      return fetch(url)
        .then((res) => res.json())
        .then((json) => json.data);
    },
  });

  return (
    <LogAnalysisContext.Provider value={{ isLoading, error, data }}>
      {children}
    </LogAnalysisContext.Provider>
  );
};

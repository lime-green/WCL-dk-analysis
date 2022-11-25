import axios from "axios";
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
        return Promise.reject("Missing required parameters");
      }

      const url = `${ANALYSIS_URL}?${new URLSearchParams({
        source_id,
        fight_id,
        report_id,
      })}`;
      return new Promise((resolve) => setTimeout(resolve, 500))
        .then(() => axios.get(url, { timeout: 10000 }))
        .then((res) => res.data.data)
        .catch((e) => {
          if (e.response) {
            return Promise.reject(`HTTP error (${e.response.status})`);
          }
          if (e.code === "ECONNABORTED") {
            return Promise.reject("Request timed out");
          }
          if (e.name === "AxiosError") {
            return Promise.reject(e.message);
          }
          return Promise.reject(String(e));
        });
    },
  });

  return (
    <LogAnalysisContext.Provider value={{ isLoading, error, data }}>
      {children}
    </LogAnalysisContext.Provider>
  );
};

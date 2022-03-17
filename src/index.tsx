import React from "react";
import ReactDOM from "react-dom";
import * as Sentry from "@sentry/react";
import { BrowserTracing } from "@sentry/tracing";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ApolloProvider } from "@apollo/client";
import { Toaster } from "react-hot-toast";
import "./index.scss";
import apolloClient from "lib/apolloClient";
import reportWebVitals from "./reportWebVitals";
import App from "./App";

Sentry.init({
  dsn: "https://31c57d6c23f24a448fc6df1984a3cfd6@o502963.ingest.sentry.io/6263026",
  integrations: [new BrowserTracing()],

  // Set tracesSampleRate to 1.0 to capture 100%
  // of transactions for performance monitoring.
  // We recommend adjusting this value in production
  tracesSampleRate: 0.5,
});

ReactDOM.render(
  <React.StrictMode>
    <ApolloProvider client={apolloClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/duel/:duelId" element={<App />} />
        </Routes>
      </BrowserRouter>
    </ApolloProvider>
    <Toaster />
  </React.StrictMode>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();

import React from "react";
import ReactDOM from "react-dom";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ApolloProvider } from "@apollo/client";
import { Toaster } from "react-hot-toast";
import "./index.scss";
import apolloClient from "lib/apolloClient";
import reportWebVitals from "./reportWebVitals";
import App from "./App";

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

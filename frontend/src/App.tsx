import {
  BrowserRouter,
  Routes,
  Route,
} from "react-router-dom";

import Layout from "./components/Layout";

import Dashboard from "./pages/Dashboard";
import Professionals from "./pages/Professionals";
import Imports from "./pages/Imports";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        <Route element={<Layout />}>

          <Route
            path="/"
            element={<Dashboard />}
          />

          <Route
            path="/professionals"
            element={<Professionals />}
          />

          <Route
            path="/imports"
            element={<Imports />}
          />

        </Route>

      </Routes>
    </BrowserRouter>
  );
}
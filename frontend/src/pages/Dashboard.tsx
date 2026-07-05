import { useEffect, useState } from "react";

import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";

import SummaryCard from "../components/SummaryCard";

import type { DashboardSummary } from "../types/dashboard";

import { getDashboardSummary } from "../services/dashboardService";

export default function Dashboard() {
  const [summary, setSummary] =
    useState<DashboardSummary | null>(null);

  useEffect(() => {
    getDashboardSummary()
      .then((data) => {
        setSummary(data);
      })
      .catch((error) => {
        console.error(error);
      });
  }, []);

  if (!summary) {
    return (
      <Container sx={{ mt: 5 }}>
        <Typography variant="h5">
          Loading...
        </Typography>
      </Container>
    );
  }

  return (
    <Container sx={{ mt: 5 }}>
      <Typography variant="h3" gutterBottom>
        Cyber Workforce Intelligence
      </Typography>

      <Box
        sx={{
          display: "flex",
          gap: 3,
          flexWrap: "wrap",
        }}
      >
        <SummaryCard
          title="Professionals"
          value={summary.professionals}
        />

        <SummaryCard
          title="Companies"
          value={summary.companies}
        />

        <SummaryCard
          title="Skills"
          value={summary.skills}
        />

        <SummaryCard
          title="Imports"
          value={summary.imports}
        />
      </Box>
    </Container>
  );
}
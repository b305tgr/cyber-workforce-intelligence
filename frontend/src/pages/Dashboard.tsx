import { useEffect, useState } from "react";

import {
  Container,
  Typography,
  Box,
  Button,
  Stack,
} from "@mui/material";

import { Link } from "react-router-dom";

import SummaryCard from "../components/SummaryCard";

import type { DashboardSummary } from "../types/dashboard";

import {
  getDashboardSummary,
} from "../services/dashboardService";

export default function Dashboard() {

  const [summary, setSummary] =
    useState<DashboardSummary | null>(null);

  const [lastUpdated, setLastUpdated] =
    useState("");

  useEffect(() => {

    getDashboardSummary().then((data) => {

      setSummary(data);

      setLastUpdated(
        new Date().toLocaleString()
      );

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

    <Container>

      <Typography
        variant="h3"
        gutterBottom
      >
        Cyber Workforce Intelligence
      </Typography>

      <Typography
        color="text.secondary"
        sx={{ mb: 3 }}
      >
        Operational Dashboard
      </Typography>

      <Stack
        direction="row"
        spacing={2}
        sx={{ mb: 4 }}
      >

        <Button
          component={Link}
          to="/professionals"
          variant="contained"
        >
          Professionals
        </Button>

        <Button
          component={Link}
          to="/imports"
          variant="outlined"
        >
          Import History
        </Button>

      </Stack>

      <Box
        sx={{
          display: "flex",
          flexWrap: "wrap",
          gap: 3,
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
          title="Certifications"
          value={summary.certifications}
        />

        <SummaryCard
          title="Imports"
          value={summary.imports}
        />

      </Box>

      <Typography
        sx={{
          mt: 4,
          color: "gray",
        }}
      >
        Last Updated: {lastUpdated}
      </Typography>

    </Container>

  );

}
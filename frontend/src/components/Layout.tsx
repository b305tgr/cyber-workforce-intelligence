import { Outlet, Link } from "react-router-dom";

import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Container,
} from "@mui/material";

export default function Layout() {
  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography
            variant="h6"
            sx={{ flexGrow: 1 }}
          >
            Cyber Workforce Intelligence
          </Typography>

          <Button
            color="inherit"
            component={Link}
            to="/"
          >
            Dashboard
          </Button>

          <Button
            color="inherit"
            component={Link}
            to="/professionals"
          >
            Professionals
          </Button>

          <Button
            color="inherit"
            component={Link}
            to="/imports"
          >
            Imports
          </Button>
        </Toolbar>
      </AppBar>

      <Container sx={{ mt: 4 }}>
        <Outlet />
      </Container>
    </>
  );
}
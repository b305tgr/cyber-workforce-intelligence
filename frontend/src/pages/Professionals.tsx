import { useEffect, useMemo, useState } from "react";

import {
  Container,
  Typography,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  TextField,
  Stack,
  Button,
} from "@mui/material";

import type { Professional } from "../types/professional";

import {
  getProfessionals,
  deleteProfessional,
} from "../services/professionalService";

import ProfessionalDialog from "../components/ProfessionalDialog";

export default function Professionals() {

  const [professionals, setProfessionals] =
    useState<Professional[]>([]);

  const [search, setSearch] =
    useState("");

  const [dialogOpen, setDialogOpen] =
    useState(false);

  async function loadProfessionals() {

    const data =
      await getProfessionals();

    setProfessionals(data);

  }

  async function handleDelete(
    id: string,
  ) {

    const confirmed =
      window.confirm(
        "Delete this professional?"
      );

    if (!confirmed) return;

    await deleteProfessional(id);

    await loadProfessionals();

  }

  useEffect(() => {

    loadProfessionals();

  }, []);

  const filtered = useMemo(() => {

    const text =
      search.toLowerCase();

    return professionals.filter((p) =>

      p.full_name
        .toLowerCase()
        .includes(text) ||

      (p.current_title ?? "")
        .toLowerCase()
        .includes(text)

    );

  }, [professionals, search]);

  return (

    <Container>

      <Typography
        variant="h4"
        gutterBottom
      >
        Professionals
      </Typography>

      <Stack
        direction="row"
        spacing={2}
        sx={{ mb: 3 }}
      >

        <TextField
          label="Search Professional"
          value={search}
          onChange={(e) =>
            setSearch(
              e.target.value
            )
          }
          fullWidth
        />

        <Button
          variant="contained"
          onClick={() =>
            setDialogOpen(true)
          }
        >
          Add
        </Button>

      </Stack>

      <Paper>

        <Table>

          <TableHead>

            <TableRow>

              <TableCell>
                <strong>Name</strong>
              </TableCell>

              <TableCell>
                <strong>Title</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Experience</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Actions</strong>
              </TableCell>

            </TableRow>

          </TableHead>

          <TableBody>

            {filtered.map((professional) => (

              <TableRow
                key={professional.id}
              >

                <TableCell>
                  {professional.full_name}
                </TableCell>

                <TableCell>
                  {professional.current_title}
                </TableCell>

                <TableCell align="center">
                  {professional.years_experience}
                </TableCell>

                <TableCell align="center">

                  <Button
                    size="small"
                  >
                    View
                  </Button>

                  <Button
                    size="small"
                  >
                    Edit
                  </Button>

                  <Button
                    size="small"
                    color="error"
                    onClick={() =>
                      handleDelete(
                        professional.id
                      )
                    }
                  >
                    Delete
                  </Button>

                </TableCell>

              </TableRow>

            ))}

          </TableBody>

        </Table>

      </Paper>

      <ProfessionalDialog

        open={dialogOpen}

        onClose={() =>
          setDialogOpen(false)
        }

        onSaved={
          loadProfessionals
        }

      />

    </Container>

  );

}
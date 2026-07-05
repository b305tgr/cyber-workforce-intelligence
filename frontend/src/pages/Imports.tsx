import { useEffect, useState } from "react";

import {
  Container,
  Typography,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
} from "@mui/material";

import type { ImportHistory } from "../types/import";

import {
  getImportHistory,
} from "../services/importService";

export default function Imports() {

  const [history, setHistory] = useState<ImportHistory[]>([]);

  useEffect(() => {
    getImportHistory().then(setHistory);
  }, []);

  return (
    <Container>

      <Typography
        variant="h4"
        gutterBottom
      >
        Import History
      </Typography>

      <Paper>

        <Table>

          <TableHead>

            <TableRow>

              <TableCell>
                <strong>File</strong>
              </TableCell>

              <TableCell>
                <strong>Type</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Total</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Inserted</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Duplicates</strong>
              </TableCell>

              <TableCell align="center">
                <strong>Errors</strong>
              </TableCell>

              <TableCell>
                <strong>Status</strong>
              </TableCell>

            </TableRow>

          </TableHead>

          <TableBody>

            {history.map((item) => (

              <TableRow key={item.id}>

                <TableCell>
                  {item.file_name}
                </TableCell>

                <TableCell>
                  {item.import_type}
                </TableCell>

                <TableCell align="center">
                  {item.total_records}
                </TableCell>

                <TableCell align="center">
                  {item.inserted_records}
                </TableCell>

                <TableCell align="center">
                  {item.duplicate_records}
                </TableCell>

                <TableCell align="center">
                  {item.error_records}
                </TableCell>

                <TableCell>
                  {item.status}
                </TableCell>

              </TableRow>

            ))}

          </TableBody>

        </Table>

      </Paper>

    </Container>
  );
}
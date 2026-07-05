import { useState } from "react";

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Stack,
} from "@mui/material";

import {
  createProfessional,
} from "../services/professionalService";

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export default function ProfessionalDialog({
  open,
  onClose,
  onSaved,
}: Props) {

  const [fullName, setFullName] = useState("");
  const [title, setTitle] = useState("");
  const [experience, setExperience] = useState(0);

  async function handleSave() {

    await createProfessional({

      full_name: fullName,

      current_title: title,

      years_experience: experience,

      current_company_id: null,

      location_id: null,

    });

    onSaved();

    onClose();

    setFullName("");
    setTitle("");
    setExperience(0);

  }

  return (

    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
    >

      <DialogTitle>
        Add Professional
      </DialogTitle>

      <DialogContent>

        <Stack
          spacing={2}
          sx={{ mt: 1 }}
        >

          <TextField
            label="Full Name"
            value={fullName}
            onChange={(e) =>
              setFullName(e.target.value)
            }
          />

          <TextField
            label="Current Title"
            value={title}
            onChange={(e) =>
              setTitle(e.target.value)
            }
          />

          <TextField
            label="Years Experience"
            type="number"
            value={experience}
            onChange={(e) =>
              setExperience(
                Number(e.target.value)
              )
            }
          />

        </Stack>

      </DialogContent>

      <DialogActions>

        <Button
          onClick={onClose}
        >
          Cancel
        </Button>

        <Button
          variant="contained"
          onClick={handleSave}
        >
          Save
        </Button>

      </DialogActions>

    </Dialog>

  );

}
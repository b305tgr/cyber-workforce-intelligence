import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";

type Props = {

  title: string;

  value: number;

};

export default function SummaryCard({

  title,

  value,

}: Props) {

  return (

    <Card
      sx={{
        width: 220,
      }}
    >

      <CardContent>

        <Typography
          variant="subtitle1"
          color="text.secondary"
        >
          {title}
        </Typography>

        <Typography
          variant="h3"
        >
          {value}
        </Typography>

      </CardContent>

    </Card>

  );

}
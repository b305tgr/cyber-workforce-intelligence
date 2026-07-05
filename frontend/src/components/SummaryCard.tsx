import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";

type SummaryCardProps = {
  title: string;
  value: number;
};

export default function SummaryCard({
  title,
  value,
}: SummaryCardProps) {
  return (
    <Card sx={{ minWidth: 220 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>

        <Typography variant="h3">
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}
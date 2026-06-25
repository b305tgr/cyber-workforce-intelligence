from src.etl.models.professional_record import ProfessionalRecord


class ProfessionalValidator:

    def validate(self, record: dict):

        model = ProfessionalRecord(**record)

        return model
import pandas as pd

from src.etl.parsers.base_parser import BaseParser


class CSVParser(BaseParser):

    def parse(self, file_path: str):

        df = pd.read_csv(file_path)

        return df.to_dict(orient="records")
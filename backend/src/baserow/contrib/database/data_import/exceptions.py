class ImportSchemaMismatch(Exception):
    """
    Raised when the columns of an imported file don't line up exactly with the
    importable fields of the table it is imported into. Only raised for the import
    modes listed in `STRICT_IMPORT_MODES`.
    """

    def __init__(
        self,
        unmapped_file_columns: list[str] | None = None,
        uncovered_fields: list[str] | None = None,
        duplicate_fields: list[str] | None = None,
    ):
        self.unmapped_file_columns = unmapped_file_columns or []
        self.uncovered_fields = uncovered_fields or []
        self.duplicate_fields = duplicate_fields or []
        super().__init__(
            "The columns of the file don't match the fields of the table. "
            f"Unmapped file columns: {self.unmapped_file_columns}. "
            f"Fields not covered by the file: {self.uncovered_fields}. "
            f"Fields mapped more than once: {self.duplicate_fields}."
        )

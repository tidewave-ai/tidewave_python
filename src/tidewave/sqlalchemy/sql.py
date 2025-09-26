from typing import Any, Callable, Optional

from sqlalchemy.engine import Engine

LIMIT = 50


def execute_sql_query(engine: Engine) -> Callable[[str, Optional[list[Any]]], str]:
    def execute_sql_query(query: str, arguments: Optional[list[Any]] = None) -> str:
        """
        Executes the given SQL query using SQLAlchemy engine.
        Returns the result as a Python data structure.

        The database backend is determined by the SQLAlchemy engine configuration.
        This tool works with any SQLAlchemy-supported databases.

        Note that the output is limited to 50 rows at a time. If you need to see more, perform
        additional calls using LIMIT and OFFSET in the query. If you know that only specific
        columns are relevant, only include those in the SELECT clause.

        You can use this tool to select user data, manipulate entries, and introspect the
        application data domain.

        Arguments:
          * `query`: The SQL query to execute. Use ? for parameter placeholders.
          * `arguments`: The arguments to pass to the query. The query must contain
            parameter placeholders corresponding the underlying database.
        """
        if arguments is None:
            arguments = []

        with engine.connect() as connection:
            if arguments:
                result = connection.exec_driver_sql(query, tuple(arguments))
            else:
                result = connection.exec_driver_sql(query)

            # Commit the transaction for data persistence
            connection.commit()

            # Check if this query returns data
            if result.returns_rows:
                # Get column names
                columns = list(result.keys())

                # Fetch all results to check if we need to limit
                all_rows = result.fetchall()
                num_rows = len(all_rows)

                if num_rows > LIMIT:
                    preamble = (
                        f"Query returned {num_rows} rows. Only the first {LIMIT} rows "
                        f"are included in the result. Use LIMIT + OFFSET in your query "
                        f"to show more rows if applicable.\n\n"
                    )
                    rows = [tuple(row) for row in all_rows[:LIMIT]]
                else:
                    preamble = ""
                    rows = [tuple(row) for row in all_rows]

                # Create result structure similar to Django's result
                result_dict = {
                    "columns": columns,
                    "num_rows": len(rows),
                    "rows": rows,
                }

                return preamble + repr(result_dict)
            else:
                return "OK"

    return execute_sql_query

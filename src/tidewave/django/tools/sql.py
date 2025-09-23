from typing import Any, Optional

from django.db import connection

LIMIT = 50


def execute_sql_query(query: str, arguments: Optional[list[Any]] = None) -> str:
    """
    Executes the given SQL query using Django's database connection.
    Returns the result as a Python data structure.

    The database backend is determined by Django's DATABASES setting.
    This tool works with any Django-supported databases.

    Note that the output is limited to 50 rows at a time. If you need to see more, perform
    additional calls using LIMIT and OFFSET in the query. If you know that only specific
    columns are relevant, only include those in the SELECT clause.

    You can use this tool to select user data, manipulate entries, and introspect the
    application data domain.

    Arguments:
      * `query`: The SQL query to execute. Use %s for parameter placeholders.
      * `arguments`: The arguments to pass to the query. The query must contain
        corresponding parameter placeholders.
    """
    if arguments is None:
        arguments = []

    with connection.cursor() as cursor:
        cursor.execute(query, arguments)

        # Check if this query returns data
        if cursor.description:
            # Get column names
            columns = [col[0] for col in cursor.description]

            # Fetch all results to check if we need to limit
            all_rows = cursor.fetchall()
            num_rows = len(all_rows)

            if num_rows > LIMIT:
                preamble = (
                    f"Query returned {num_rows} rows. Only the first {LIMIT} rows "
                    f"are included in the result. Use LIMIT + OFFSET in your query "
                    f"to show more rows if applicable.\n\n"
                )
                rows = all_rows[:LIMIT]
            else:
                preamble = ""
                rows = all_rows

            # Create result structure similar to Elixir's result
            result = {
                "columns": columns,
                "num_rows": len(rows),
                "rows": rows,
            }

            return preamble + repr(result)
        else:
            return "OK"

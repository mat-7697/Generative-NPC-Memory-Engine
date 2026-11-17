"""SQL parsing, safety validation, redaction, and execution plan formatting."""

import re
from typing import Any, Dict, List, Optional, Tuple


def strip_sql_comments(sql: str) -> str:
    """Strip both block comments (/* ... */) and line comments (-- ...) from SQL text

    preserving string literals intact.
    """
    pos = 0
    length = len(sql)
    result = []
    in_single_quote = False
    in_double_quote = False
    in_dollar_quote: Optional[str] = None

    while pos < length:
        # Check dollar quotes $$...$$ or $tag$...$tag$
        if not in_single_quote and not in_double_quote and in_dollar_quote is None and sql[pos] == "$":
            match = re.match(r"\$[a-zA-Z0-9_]*\$", sql[pos:])
            if match:
                in_dollar_quote = match.group(0)
                result.append(in_dollar_quote)
                pos += len(in_dollar_quote)
                continue

        if in_dollar_quote is not None:
            if sql[pos:].startswith(in_dollar_quote):
                result.append(in_dollar_quote)
                pos += len(in_dollar_quote)
                in_dollar_quote = None
                continue
            result.append(sql[pos])
            pos += 1
            continue

        char = sql[pos]

        # Handle string literals
        if char == "'" and not in_double_quote:
            # Check for escaped quote ''
            if in_single_quote and pos + 1 < length and sql[pos + 1] == "'":
                result.append("''")
                pos += 2
                continue
            in_single_quote = not in_single_quote
            result.append(char)
            pos += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
            pos += 1
            continue

        if not in_single_quote and not in_double_quote:
            # Check line comment
            if sql[pos : pos + 2] == "--":
                # Skip to end of line
                newline_pos = sql.find("\n", pos + 2)
                if newline_pos == -1:
                    break
                pos = newline_pos + 1
                result.append("\n")
                continue

            # Check block comment
            if sql[pos : pos + 2] == "/*":
                end_comment = sql.find("*/", pos + 2)
                if end_comment == -1:
                    break
                pos = end_comment + 2
                continue

        result.append(char)
        pos += 1

    return "".join(result).strip()


def check_multiple_statements(clean_sql: str) -> bool:
    """Check if the cleaned SQL string contains multiple statements separated by semicolons."""
    # Split on semicolons that are outside quotes
    pos = 0
    length = len(clean_sql)
    in_single_quote = False
    in_double_quote = False
    in_dollar_quote: Optional[str] = None
    semicolons = 0

    while pos < length:
        if not in_single_quote and not in_double_quote and in_dollar_quote is None and clean_sql[pos] == "$":
            match = re.match(r"\$[a-zA-Z0-9_]*\$", clean_sql[pos:])
            if match:
                in_dollar_quote = match.group(0)
                pos += len(in_dollar_quote)
                continue

        if in_dollar_quote is not None:
            if clean_sql[pos:].startswith(in_dollar_quote):
                pos += len(in_dollar_quote)
                in_dollar_quote = None
                continue
            pos += 1
            continue

        char = clean_sql[pos]
        if char == "'" and not in_double_quote:
            if in_single_quote and pos + 1 < length and clean_sql[pos + 1] == "'":
                pos += 2
                continue
            in_single_quote = not in_single_quote
            pos += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            pos += 1
            continue

        if not in_single_quote and not in_double_quote:
            if char == ";":
                # Check if there is meaningful SQL after this semicolon
                remainder = clean_sql[pos + 1 :].strip()
                if remainder:
                    return True
        pos += 1

    return False


def inspect_sql_statement(clean_sql: str) -> Dict[str, Any]:
    """Inspect and classify SQL statement safety, mutation type, and read-only eligibility."""
    normalized = clean_sql.strip()
    if not normalized:
        return {
            "valid": False,
            "error": "SQL statement is empty",
            "category": "EMPTY",
            "is_read_only": False,
            "is_dml": False,
            "is_ddl": False,
        }

    # Extract first keyword
    tokens = normalized.split()
    first_keyword = tokens[0].upper()

    # DDL detection
    ddl_keywords = {"DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"}
    if first_keyword in ddl_keywords:
        return {
            "valid": True,
            "category": "DDL",
            "first_keyword": first_keyword,
            "is_read_only": False,
            "is_dml": False,
            "is_ddl": True,
            "has_mutation": True,
        }

    # DML detection (INSERT, UPDATE, DELETE)
    dml_keywords = {"INSERT", "UPDATE", "DELETE", "CALL"}
    if first_keyword in dml_keywords:
        return {
            "valid": True,
            "category": "DML",
            "first_keyword": first_keyword,
            "is_read_only": False,
            "is_dml": True,
            "is_ddl": False,
            "has_mutation": True,
        }

    # EXPLAIN queries
    if first_keyword == "EXPLAIN":
        # Check if the explained query contains mutations (EXPLAIN ANALYZE INSERT ...)
        has_sub_mutation = bool(
            re.search(r"\b(INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM)\b", normalized, re.IGNORECASE)
        )
        return {
            "valid": True,
            "category": "EXPLAIN",
            "first_keyword": first_keyword,
            "is_read_only": not has_sub_mutation,
            "is_dml": False,
            "is_ddl": False,
            "has_mutation": has_sub_mutation,
        }

    # CTE (WITH or WITH RECURSIVE)
    if first_keyword == "WITH":
        # Check if CTE contains data-modifying statements (INSERT, UPDATE, DELETE)
        # e.g., WITH moved AS (DELETE FROM ...)
        has_mutation = bool(
            re.search(
                r"\b(INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|DROP\s+TABLE|TRUNCATE)\b",
                normalized,
                re.IGNORECASE,
            )
        )
        return {
            "valid": True,
            "category": "CTE",
            "first_keyword": first_keyword,
            "is_read_only": not has_mutation,
            "is_dml": has_mutation,
            "is_ddl": False,
            "has_mutation": has_mutation,
        }

    # Pure read-only queries
    read_only_keywords = {"SELECT", "TABLE", "VALUES", "SHOW"}
    if first_keyword in read_only_keywords:
        return {
            "valid": True,
            "category": "SELECT",
            "first_keyword": first_keyword,
            "is_read_only": True,
            "is_dml": False,
            "is_ddl": False,
            "has_mutation": False,
        }

    # Other statements
    return {
        "valid": True,
        "category": "OTHER",
        "first_keyword": first_keyword,
        "is_read_only": False,
        "is_dml": False,
        "is_ddl": False,
        "has_mutation": False,
    }


def redact_sensitive_columns(columns: List[str], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact passwords, secret hashes, and credentials in query result rows."""
    sensitive_patterns = {"password_hash", "password", "secret", "jwt_secret", "hash"}
    cols_to_redact = [col for col in columns if col.lower() in sensitive_patterns]

    if not cols_to_redact:
        return rows

    redacted_rows = []
    for row in rows:
        new_row = dict(row)
        for col in cols_to_redact:
            if col in new_row and new_row[col] is not None:
                new_row[col] = "[REDACTED_PASSWORD_HASH]"
        redacted_rows.append(new_row)
    return redacted_rows


def format_plan_tree(plan_node: Dict[str, Any], depth: int = 0) -> List[str]:
    """Construct an ASCII tree representation of the query plan from JSON EXPLAIN output."""
    lines = []
    prefix = "  " * depth
    node_type = plan_node.get("Node Type", "Plan")
    relation = plan_node.get("Relation Name")
    alias = plan_node.get("Alias")
    index_name = plan_node.get("Index Name")
    startup_cost = plan_node.get("Startup Cost", 0.0)
    total_cost = plan_node.get("Total Cost", 0.0)
    plan_rows = plan_node.get("Plan Rows", 0)
    actual_rows = plan_node.get("Actual Rows")
    actual_time = plan_node.get("Actual Total Time")
    loops = plan_node.get("Actual Loops", 1)

    desc_parts = [node_type]
    if index_name:
        desc_parts.append(f"using {index_name}")
    if relation:
        if alias and alias != relation:
            desc_parts.append(f"on {relation} {alias}")
        else:
            desc_parts.append(f"on {relation}")

    cost_str = f"(cost={startup_cost:.2f}..{total_cost:.2f} rows={plan_rows}"
    if actual_rows is not None and actual_time is not None:
        cost_str += f" actual time={actual_time:.3f} rows={actual_rows} loops={loops})"
    else:
        cost_str += ")"

    arrow = "->  " if depth > 0 else ""
    lines.append(f"{prefix}{arrow}{' '.join(desc_parts)}  {cost_str}")

    # Output columns if present
    if "Output" in plan_node and depth == 0:
        output_cols = ", ".join(plan_node["Output"][:8])
        if len(plan_node["Output"]) > 8:
            output_cols += f" ... (+{len(plan_node['Output']) - 8} more)"
        lines.append(f"{prefix}    Output: {output_cols}")

    # Filter conditions
    if "Filter" in plan_node:
        lines.append(f"{prefix}    Filter: {plan_node['Filter']}")
        if "Rows Removed by Filter" in plan_node:
            lines.append(f"{prefix}    Rows Removed by Filter: {plan_node['Rows Removed by Filter']}")

    if "Index Cond" in plan_node:
        lines.append(f"{prefix}    Index Cond: {plan_node['Index Cond']}")

    # Shared buffers
    hit = plan_node.get("Shared Hit Blocks", 0)
    read = plan_node.get("Shared Read Blocks", 0)
    if hit > 0 or read > 0:
        lines.append(f"{prefix}    Buffers: shared hit={hit} read={read}")

    # Recurse children plans
    for child in plan_node.get("Plans", []):
        lines.extend(format_plan_tree(child, depth + 1))

    return lines

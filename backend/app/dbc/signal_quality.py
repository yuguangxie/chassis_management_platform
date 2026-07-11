def quality_from_parse_status(parse_status: str) -> str:
    return 'good' if parse_status == 'ok' else 'invalid'

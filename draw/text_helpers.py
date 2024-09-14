def truncate(text, truncate_at):
    if len(text) >= truncate_at:
        return text[:truncate_at] + "..."
    else:
        return text

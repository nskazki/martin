def truncate(text, truncate_at):
    uppercased = sum(1 for char in text if char.isupper())
    truncate_at -= uppercased

    if len(text) >= truncate_at:
        return text[:truncate_at] + "..."
    else:
        return text

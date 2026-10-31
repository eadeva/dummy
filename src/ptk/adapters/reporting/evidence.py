"""Mask structured evidence before JSON encoding can escape a secret."""


def mask_data(value, mask):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, dict):
        return {mask(str(key)): mask_data(item, mask) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_data(item, mask) for item in value]
    return value

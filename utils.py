def calculate_average(numbers):
    if not numbers:  # guards against None and empty list (ZeroDivisionError / TypeError)
        return None
    total = 0
    for num in numbers:
        if not isinstance(num, (int, float)):  # guards against non-numeric items (TypeError)
            raise TypeError(f"All elements must be numeric, got {type(num).__name__!r}")
        total += num
    return total / len(numbers)


def get_user_name(user):
    if user is None:  # guards against None input (TypeError)
        return ""
    name = user.get("name")  # guards against missing key (KeyError)
    if name is None:
        return ""
    return str(name).upper()  # str() guards against non-string name (AttributeError)
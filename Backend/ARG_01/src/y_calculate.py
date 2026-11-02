
def calculate_vertical_angles(y_bottom: int, frame_height: int = 480) -> tuple[int, int]:
    y_min, y_max = 180, 440

    clamped_y = max(y_min, min(y_max, y_bottom))

    norm = (clamped_y - y_min) / (y_max - y_min)

    s1 = int(30 + norm * 25)
    s2 = int(45 + norm * 35)

    return s1, s2
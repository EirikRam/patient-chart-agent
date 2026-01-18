import inspect

from packages.core.schemas import chart


def main() -> None:
    print(chart.__file__)
    print(hasattr(chart, "PatientChart"))
    class_names = [
        name
        for name, obj in inspect.getmembers(chart, inspect.isclass)
        if obj.__module__ == chart.__name__
    ]
    print(class_names)


if __name__ == "__main__":
    main()
